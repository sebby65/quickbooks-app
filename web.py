import os
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from prophet import Prophet
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# QuickBooks credentials (fill CLIENT_SECRET in .env)
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")  # Will update after first auth
REALM_ID = os.getenv("QB_REALM_ID")           # Will capture on first auth

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# Step 1: Exchange refresh token for a fresh access token
def get_access_token():
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    r = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    token_data = r.json()
    return token_data.get("access_token")

# Step 2: Fetch Profit & Loss Report from QuickBooks
def fetch_pnl_report(start_date="2024-01-01", end_date="2024-06-30"):
    access_token = get_access_token()
    url = f"https://quickbooks.api.intuit.com/v3/company/{REALM_ID}/reports/ProfitAndLoss"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {"start_date": start_date, "end_date": end_date}

    r = requests.get(url, headers=headers, params=params)
    report = r.json()

    if not report.get("Rows") or not report["Rows"].get("Row"):
        return None
    return report

# Step 3: Convert QuickBooks JSON into DataFrame
def report_to_df(report):
    rows = report["Rows"]["Row"]
    data = []
    for row in rows:
        if "ColData" in row:
            name = row["ColData"][0]["value"]
            value = float(row["ColData"][1]["value"].replace(",", "")) if len(row["ColData"]) > 1 else 0.0
            data.append({"Account": name, "Amount": value})
    return pd.DataFrame(data)

# Step 4: Forecast Net Income
def forecast_net_income(df):
    df["NetIncome"] = df["Amount"]
    df["Month"] = pd.date_range("2024-01-01", periods=len(df), freq="M")

    forecast_df = pd.DataFrame({"ds": df["Month"], "y": df["NetIncome"]})
    model = Prophet()
    model.fit(forecast_df)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    combined = pd.DataFrame({"Month": forecast["ds"], "PredictedNetIncome": forecast["yhat"]})
    return combined

# Step 5: Create Forecast Chart
def create_chart(df, forecast_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Month"], y=df["Amount"], mode="lines+markers", name="Actual Net Income"))
    future_part = forecast_df[forecast_df["Month"] > df["Month"].max()]
    fig.add_trace(go.Scatter(x=future_part["Month"], y=future_part["PredictedNetIncome"], mode="lines+markers", name="Forecasted Net Income"))
    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD")
    fig.write_html("forecast.html", auto_open=False)

# ---- Routes ----

# Root Dashboard
@app.route("/")
def index():
    return """
    <h1>Financial Forecast Dashboard</h1>
    <p><a href="/auth">Authorize QuickBooks</a></p>
    <p><a href="/pnl">View P&L JSON</a></p>
    <p><a href="/forecast">Generate Forecast Chart</a></p>
    """
@app.route("/auth")
def auth_route():
    # Build QuickBooks authorization URL
    base_url = "https://appcenter.intuit.com/connect/oauth2"
    redirect_uri = "https://quickbooks-app-3.onrender.com/callback"
    scope = "com.intuit.quickbooks.accounting"
    state = "secureRandomState"  # Can be anything, just for verification

    auth_url = (
        f"{base_url}?client_id={CLIENT_ID}"
        f"&response_type=code&scope={scope}"
        f"&redirect_uri={redirect_uri}&state={state}"
    )

    # Redirect user to QuickBooks login
    return f'<meta http-equiv="refresh" content="0; URL={auth_url}" />'

# OAuth Redirect Handler — captures code and realmId, exchanges for tokens
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
    access_token = tokens.get("access_token")
    REALM_ID = realm_id

    return f"""
    <h2>QuickBooks Connection Successful!</h2>
    <p><b>Realm ID:</b> {REALM_ID}</p>
    <p><b>Refresh Token:</b> {REFRESH_TOKEN}</p>
    <p><b>Access Token (temporary):</b> {access_token}</p>
    <p>Save the Realm ID and Refresh Token into your .env file.</p>
    <p><a href="/">Back to Dashboard</a></p>
    """

# Profit & Loss JSON
@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    if not report:
        return jsonify({"error": "No Profit & Loss data found. Seed invoices/expenses first."})
    df = report_to_df(report)
    return jsonify(df.to_dict(orient="records"))

# Forecast Chart
@app.route("/forecast")
def forecast_route():
    report = fetch_pnl_report()
    if not report:
        return jsonify({"error": "No Profit & Loss data found."})
    df = report_to_df(report)
    forecast_df = forecast_net_income(df)
    create_chart(df, forecast_df)
    return send_file("forecast.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
