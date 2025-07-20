import os
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from prophet import Prophet
import plotly.graph_objects as go
from dotenv import load_dotenv
from datetime import datetime  # <-- FIXED (was missing before)

load_dotenv()

app = Flask(__name__)

# QuickBooks credentials
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# --- Helper: Save updated tokens to .env automatically ---
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

# --- Get a fresh Access Token using Refresh Token ---
def get_access_token():
    global REFRESH_TOKEN
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    r = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    token_data = r.json()

    if "refresh_token" in token_data:
        REFRESH_TOKEN = token_data["refresh_token"]
        save_to_env("QB_REFRESH_TOKEN", REFRESH_TOKEN)

    return token_data.get("access_token")

# --- Fetch Profit & Loss Report (YTD) ---
def fetch_pnl_report():
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

# --- Convert JSON report to DataFrame (Revenue, Expenses, Net Income) ---
def report_to_df(report):
    rows = report["Rows"]["Row"]
    totals = {"Revenue": 0.0, "Expenses": 0.0, "NetIncome": 0.0}

    for row in rows:
        if "ColData" in row:
            name = row["ColData"][0]["value"].lower()
            value = float(row["ColData"][1]["value"].replace(",", "")) if len(row["ColData"]) > 1 else 0.0

            if "gross profit" in name or "income" in name:
                totals["Revenue"] += value
            elif "expense" in name:
                totals["Expenses"] += value
            elif "net operating income" in name or "net income" in name:
                totals["NetIncome"] = value

    if totals["NetIncome"] == 0.0:
        totals["NetIncome"] = totals["Revenue"] - totals["Expenses"]

    months = pd.date_range(f"{datetime.now().year}-01-01", periods=6, freq="M")
    df = pd.DataFrame({
        "Month": months,
        "Revenue": [totals["Revenue"] / 6] * 6,
        "Expenses": [totals["Expenses"] / 6] * 6,
        "NetIncome": [totals["NetIncome"] / 6] * 6,
    })
    return df

# --- Forecast Revenue, Expenses, Net Income ---
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

# --- Create interactive chart with actuals + forecast ---
def create_chart(df, forecasts):
    fig = go.Figure()

    for col in ["Revenue", "Expenses", "NetIncome"]:
        fig.add_trace(go.Scatter(x=df["Month"], y=df[col], mode="lines+markers", name=f"Actual {col}"))
        future_part = forecasts[col][forecasts[col]["ds"] > df["Month"].max()]
        fig.add_trace(go.Scatter(x=future_part["ds"], y=future_part["yhat"], mode="lines+markers", name=f"Forecasted {col}"))

    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD")
    fig.write_html("forecast.html", auto_open=False)

# --- ROUTES ---

@app.route("/")
def index():
    return """
    <h1>Financial Forecast Dashboard</h1>
    <p><a href="/auth">Authorize QuickBooks</a></p>
    <p><a href="/pnl">View P&L JSON</a></p>
    <p><a href="/forecast">Generate Forecast Dashboard</a></p>
    """

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

@app.route("/callback")
def callback():
    global REFRESH_TOKEN, REALM_ID
    code = request.args.get("code")
    realm_id = request.args.get("realmId")

    if not code:
        return "No authorization code received.", 400

    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": "https://quickbooks-app-3.onrender.com/callback"}

    r = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    tokens = r.json()

    REFRESH_TOKEN = tokens.get("refresh_token")
    REALM_ID = realm_id
    save_to_env("QB_REFRESH_TOKEN", REFRESH_TOKEN)
    save_to_env("QB_REALM_ID", REALM_ID)

    return "<h2>QuickBooks Connected!</h2><p>Tokens saved. You can now use /pnl and /forecast.</p>"

@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    if not report:
        return jsonify({"error": "No Profit & Loss data found. Add invoices/expenses first."})
    df = report_to_df(report)
    return jsonify(df.to_dict(orient="records"))

@app.route("/forecast")
def forecast_route():
    report = fetch_pnl_report()
    if not report:
        return "<h2>No P&L data found. Seed QuickBooks with invoices and expenses.</h2>"

    df = report_to_df(report)
    forecasts = forecast_metrics(df)
    create_chart(df, forecasts)

    last_row = df.iloc[-1]
    avg_net = forecasts["NetIncome"]["yhat"].tail(3).mean()

    return f"""
    <h2>Financial Forecast Summary</h2>
    <p><b>Last Month (June):</b><br>
    Revenue: ${last_row['Revenue']:.2f}<br>
    Expenses: ${last_row['Expenses']:.2f}<br>
    Net Income: ${last_row['NetIncome']:.2f}</p>
    <p><b>Forecast (Next 3 Months):</b><br>
    Avg Net Income: ${avg_net:.2f}</p>
    <iframe src="/forecast_chart" width="100%" height="600"></iframe>
    """

@app.route("/forecast_chart")
def forecast_chart():
    return send_file("forecast.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
