import os
import json
import pandas as pd
import requests
from datetime import datetime
from prophet import Prophet
from flask import Flask, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
PANDL_URL = f"https://quickbooks.api.intuit.com/v3/company/{REALM_ID}/reports/ProfitAndLoss?start_date={datetime.now().year}-01-01&end_date={datetime.now().year}-12-31"

def get_access_token():
    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN},
        headers={"Accept": "application/json"},
        auth=(CLIENT_ID, CLIENT_SECRET)
    )
    if resp.status_code != 200:
        print("QuickBooks token error:", resp.text)
        return None
    data = resp.json()
    if "refresh_token" in data:
        # Persist new refresh token so it doesn't expire
        with open(".env", "a") as f:
            f.write(f"\nQB_REFRESH_TOKEN={data['refresh_token']}")
    return data.get("access_token")

def fetch_pnl_report():
    token = get_access_token()
    if not token:
        return []
    resp = requests.get(PANDL_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    if resp.status_code != 200:
        print("QuickBooks fetch failed:", resp.text)
        return []

    # Placeholder: replace this with parsed QuickBooks JSON
    return [
        {"Month": "Jan 2025", "Revenue": 90000, "Expenses": 30000, "NetIncome": 60000},
        {"Month": "Feb 2025", "Revenue": 105000, "Expenses": 35000, "NetIncome": 70000},
        {"Month": "Mar 2025", "Revenue": 98000, "Expenses": 32000, "NetIncome": 66000},
        {"Month": "Apr 2025", "Revenue": 110000, "Expenses": 36000, "NetIncome": 74000},
        {"Month": "May 2025", "Revenue": 120000, "Expenses": 38000, "NetIncome": 82000},
        {"Month": "Jun 2025", "Revenue": 115000, "Expenses": 34000, "NetIncome": 81000},
    ]

def forecast_pnl(df):
    df = pd.DataFrame(df)
    df["Month"] = pd.to_datetime(df["Month"])
    m = Prophet()
    m.fit(df.rename(columns={"Month": "ds", "NetIncome": "y"}))
    future = m.make_future_dataframe(periods=3, freq="MS")
    forecast = m.predict(future)
    return forecast

@app.route("/")
def home():
    return render_template_string("""
        <h1>QuickBooks Forecast App</h1>
        <p><a href='/pnl'>View P&L JSON</a></p>
        <p><a href='/forecast'>View Forecast</a></p>
    """)

@app.route("/pnl")
def pnl_route():
    return json.dumps(fetch_pnl_report())

@app.route("/forecast")
def forecast_route():
    df = fetch_pnl_report()
    if not df:
        return "No data available"
    forecast = forecast_pnl(df)
    avg_future = round(forecast.tail(3)["yhat"].mean(), 2)
    return render_template_string("""
        <h1>Financial Forecast Summary</h1>
        <p>Last Month Net Income: ${{ last_net }}</p>
        <p>Forecast Avg (Next 3 Months): ${{ avg_future }}</p>
    """, last_net=df[-1]["NetIncome"], avg_future=avg_future)

if __name__ == "__main__":
    app.run(debug=True)
