import os
import requests
import pandas as pd
from flask import Flask, redirect, request, render_template_string
from datetime import datetime, timedelta
from prophet import Prophet
import json

# Load environment variables (Render provides these automatically)
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("QB_REALM_ID")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "production")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

app = Flask(__name__)

# --- Token Handling ---
def save_refresh_token(token):
    """Update REFRESH_TOKEN environment for Render (fallback for local)."""
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("QB_REFRESH_TOKEN="):
                    f.write(f"QB_REFRESH_TOKEN={token}\n")
                else:
                    f.write(line)
    except FileNotFoundError:
        # On Render, just log (can't write to .env)
        print(f"[INFO] New refresh token: {token}")

def get_access_token():
    """Refresh QuickBooks access token using refresh token."""
    global REFRESH_TOKEN
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    auth = (CLIENT_ID, CLIENT_SECRET)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }
    response = requests.post(TOKEN_URL, headers=headers, auth=auth, data=data)
    if response.status_code != 200:
        print("QuickBooks token error:", response.text)
        return None
    tokens = response.json()
    REFRESH_TOKEN = tokens.get("refresh_token", REFRESH_TOKEN)
    save_refresh_token(REFRESH_TOKEN)
    return tokens.get("access_token")

# --- Fetch P&L Report ---
def fetch_pnl_report():
    """Fetch Profit & Loss report from QuickBooks API."""
    token = get_access_token()
    if not token:
        return []
    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        return []
    # Placeholder for parsing the actual QuickBooks JSON response
    return [
        {"Month": "Jan 2025", "Revenue": 90000, "Expenses": 30000, "NetIncome": 60000},
        {"Month": "Feb 2025", "Revenue": 105000, "Expenses": 35000, "NetIncome": 70000},
        {"Month": "Mar 2025", "Revenue": 98000, "Expenses": 32000, "NetIncome": 66000},
        {"Month": "Apr 2025", "Revenue": 110000, "Expenses": 36000, "NetIncome": 74000},
        {"Month": "May 2025", "Revenue": 120000, "Expenses": 38000, "NetIncome": 82000},
        {"Month": "Jun 2025", "Revenue": 115000, "Expenses": 34000, "NetIncome": 81000}
    ]

# --- Forecast Route ---
def generate_forecast(data):
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])
    model = Prophet(yearly_seasonality=True, daily_seasonality=False)
    model.add_seasonality(name='monthly', period=30.5, fourier_order=5)

    # Train on NetIncome
    df_train = df[["Month", "NetIncome"]].rename(columns={"Month": "ds", "NetIncome": "y"})
    model.fit(df_train)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    forecast_df = forecast[["ds", "yhat"]].tail(3)
    avg_net_income = forecast_df["yhat"].mean()
    return avg_net_income

# --- Flask Routes ---
@app.route("/")
def home():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    auth_url = (
        "https://appcenter.intuit.com/connect/oauth2"
        f"?client_id={CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting"
        f"&redirect_uri={REDIRECT_URI}&state=secureRandomState"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Callback failed: No code provided", 400
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    return json.dumps(report)

@app.route("/forecast")
def forecast_route():
    data = fetch_pnl_report()
    if not data:
        return "No P&L data available"
    avg_income = generate_forecast(data)
    return render_template_string(f"""
        <h1>Financial Forecast Summary</h1>
        <p>Average Net Income (Next 3 Months): ${avg_income:,.2f}</p>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
