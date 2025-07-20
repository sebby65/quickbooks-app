import os
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from prophet import Prophet
import plotly.graph_objects as go
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Load QuickBooks credentials
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# ---- Helper: Save tokens to .env automatically ----
def save_to_env(key, value):
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()

    updated = False
    with open(env_file, "w") as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"{key}={value}\n")

# ---- Step 1: Get a fresh access token from the refresh token ----
def get_access_token():
    global REFRESH_TOKEN
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    r = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    token_data = r.json()

    # If the refresh token rotated, save the new one
    if "refresh_token" in token_data:
        REFRESH_TOKEN = token_data["refresh_token"]
        save_to_env("QB_REFRESH_TOKEN", REFRESH_TOKEN)

    return token_data.get("access_token")

# ---- Step 2: Fetch Profit & Loss Report ----
def fetch_pnl_report():
    # Get current year start to today's date
    year_start = f"{datetime.now().year}-01-01"
    today = datetime.now().strftime("%Y-%m-%d")

    access_token = get_access_token()
    url = f"https://quickbooks.api.intuit.com/v3/company/{REALM_ID}/reports/ProfitAndLoss"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {"start_date": year_start, "end_date": today}

    r = requests.get(url, headers=headers, params=params)
    report = r.json()

    if not report.get("Rows") or not report["Rows"].get("Row"):
        return None
    return report

def report_to_df(report):
    rows = report["Rows"]["Row"]
    data = {"Revenue": 0.0, "Expenses": 0.0, "NetIncome": 0.0}

    for row in rows:
        if "ColData" in row:
            name = row["ColData"][0]["value"].lower()
            value = float(row["ColData"][1]["value"].replace(",", "")) if len(row["ColData"]) > 1 else 0.0

            if "gross profit" in name or "income" in name:
                data["Revenue"] += value
            elif "expense" in name:
                data["Expenses"] += value
            elif "net operating income" in name or "net income" in name:
                data["NetIncome"] = value

    # If QuickBooks doesn't give NetIncome, calculate it
    if data["NetIncome"] == 0.0:
        data["NetIncome"] = data["Revenue"] - data["Expenses"]

    # Build DataFrame (6 months of repeated totals for Prophet)
    months = pd.date_range(f"{datetime.now().year}-01-01", periods=6, freq="M")
    df = pd.DataFrame({
        "Month": months,
        "Revenue": [data["Revenue"] / 6] * 6,
        "Expenses": [data["Expenses"] / 6] * 6,
        "NetIncome": [data["NetIncome"] / 6] * 6,
    })
    return df

# ---- Step 3: Convert JSON to a usable DataFrame ----
def report_to_df(report):
    rows = report["Rows"]["Row"]
    data = []
    for row in rows:
        if "ColData" in row:
            name = row["ColData"][0]["value"].lower()
            value = float(row["ColData"][1]["value"].replace(",", "")) if len(row["ColData"]) > 1 else 0.0
            data.append({"Category": name, "Amount": value})

    df = pd.DataFrame(data)
    # Fill missing revenue/expenses explicitly
    revenue = df[df["Category"].str.contains("income")]["Amount"].sum()
    expenses = df[df["Category"].str.contains("expense")]["Amount"].sum()
    net_income = revenue - expenses

    # Monthly timeline (seeded with 6 months data for simplicity)
    months = pd.date_range("2024-01-01", periods=6, freq="M")
    df_final = pd.DataFrame({
        "Month": months,
        "Revenue": [revenue / 6] * 6,
        "Expenses": [expenses / 6] * 6,
    })
    df_final["NetIncome"] = df_final["Revenue"] - df_final["Expenses"]
    return df_final

# ---- Step 4: Forecast each metric ----
def forecast_metrics(df):
    forecasts = {}
    for col in ["Revenue", "Expenses", "NetIncome"]:
        data = pd.DataFrame({"ds": df["Month"], "y": df[col]})
        model = Prophet()
        model.fit(data)
        future = model.make_future_dataframe(periods=3, freq="M")
        forecast = model.predict(future)
        forecasts[col] = forecast[["ds", "yhat"]]
    return forecasts

# ---- Step 5: Build Plotly Chart ----
def create_chart(df, forecasts):
    fig = go.Figure()

    # Add historicals
    for col in ["Revenue", "Expenses", "NetIncome"]:
        fig.add_trace(go.Scatter(x=df["Month"], y=df[col], mode="lines+markers", name=f"Actual {col}"))

    # Add forecasts (only future months)
    last_date = df["Month"].max()
    for col, forecast in forecasts.items():
        future_part = forecast[forecast["ds"] > last_date]
        fig.add_trace(go.Scatter(x=future_part["ds"], y=future_part["yhat"], mode="lines+markers", name=f"Forecasted {col}"))

    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD")
    fig.write_html("forecast.html", auto_open=False)

# ---- ROUTES ----

@app.route("/")
def index():
    return """
    <h1>Financial Forecast Dashboard</h1>
    <p><a href="/auth">Authorize QuickBooks</a></p>
    <p><a href="/pnl">View P&L JSON</a></p>
    <p><a href="/forecast">Generate Forecast Dashboard</a></p>
    """

# Route to start OAuth flow
@app.route("/auth")
def auth_route():
    base_url = "https://appcenter.intuit.com/connect/oauth2"
    redirect_uri = "https://quickbooks-app-3.onrender.com/callback"
    scope = "com.intuit.quickbooks.accounting"
    state = "secureRandomState"

    auth_url = (
        f"{base_url}?client_id={CLIENT_ID}"
        f"&response_type=code&scope={scope}"
        f"&redirect_uri={redirect_uri}&state={state}"
    )
    return f'<meta http-equiv="refresh" content="0; URL={auth_url}" />'

# Callback route - captures code, exchanges for tokens, saves to .env
@app.route("/callback")
def callback():
    global REFRESH_TOKEN, REALM_ID
    code = request.args.get("code")
    realm_id = request.args.get("realmId")

    if not code:
        return "No authorization code received.", 400

    # Exchange code for tokens
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://quickbooks-app-3.onrender.com/callback"
    }

    r = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    tokens = r.json()

    REFRESH_TOKEN = tokens.get("refresh_token")
    REALM_ID = realm_id
    save_to_env("QB_REFRESH_TOKEN", REFRESH_TOKEN)
    save_to_env("QB_REALM_ID", REALM_ID)

    return f"""
    <h2>QuickBooks Connected!</h2>
    <p>Realm ID and Refresh Token have been saved. You can now use /pnl and /forecast.</p>
    <p><a href="/">Back to Dashboard</a></p>
    """

# Profit & Loss JSON
@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    if not report:
        return jsonify({"error": "No Profit & Loss data found. Ensure invoices/expenses are paid."})
    df = report_to_df(report)
    return jsonify(df.to_dict(orient="records"))

# Forecast route - chart + summary
@app.route("/forecast")
def forecast_route():
    report = fetch_pnl_report()
    if not report:
        return jsonify({"error": "No Profit & Loss data found."})
    df = report_to_df(report)
    forecasts = forecast_metrics(df)
    create_chart(df, forecasts)

    # Build textual summary (last month + forecast average)
    last_row = df.iloc[-1]
    avg_net = forecasts["NetIncome"]["yhat"].tail(3).mean()
    summary_html = f"""
    <h2>Financial Forecast Summary</h2>
    <p><b>Last Actual Month (June 2024):</b><br>
    Revenue: ${last_row['Revenue']:.2f}<br>
    Expenses: ${last_row['Expenses']:.2f}<br>
    Net Income: ${last_row['NetIncome']:.2f}</p>
    <p><b>Forecast (Next 3 Months):</b><br>
    Average Net Income: ${avg_net:.2f}</p>
    <iframe src="/forecast_chart" width="100%" height="600"></iframe>
    """
    return summary_html

# Serve chart separately
@app.route("/forecast_chart")
def forecast_chart():
    return send_file("forecast.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
