import os
import json
from datetime import datetime
import requests
import pandas as pd
from flask import Flask, redirect, request, jsonify, render_template_string
from prophet import Prophet
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)

# Load environment variables
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
CLIENT_ID = os.environ.get("QB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
REALM_ID = os.environ.get("QB_REALM_ID")
REFRESH_TOKEN = os.environ.get("QB_REFRESH_TOKEN")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")

# Access token cache
ACCESS_TOKEN = None

def get_access_token():
    global ACCESS_TOKEN
    if ACCESS_TOKEN:
        return ACCESS_TOKEN

    token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()
        ACCESS_TOKEN = token_data["access_token"]
        return ACCESS_TOKEN
    return None

def fetch_pnl_report():
    """Fetch Profit & Loss report and backfill months with zeros for Prophet."""
    token = get_access_token()
    if not token:
        return []
    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    raw = response.json()

    def extract_total(group_name):
        for r in raw.get("Rows", {}).get("Row", []):
            if r.get("group") == group_name:
                coldata = r.get("Summary", {}).get("ColData") or r.get("Header", {}).get("ColData")
                if coldata and len(coldata) > 1:
                    try:
                        return float(coldata[1].get("value", 0) or 0)
                    except ValueError:
                        return 0.0
        return 0.0

    income = extract_total("Income")
    expenses = extract_total("Expenses")
    net_income = extract_total("NetIncome")

    # Backfill all months for this year so Prophet can work
    months = pd.date_range(start=f"{datetime.now().year}-01-01", end=datetime.now(), freq="MS")
    pnl_data = []
    for m in months:
        # Only fill current month with the actual values, others stay 0
        pnl_data.append({
            "Month": m.strftime("%b %Y"),
            "Revenue": income if m.month == datetime.now().month else 0,
            "Expenses": expenses if m.month == datetime.now().month else 0,
            "NetIncome": net_income if m.month == datetime.now().month else 0
        })
    return pnl_data

def build_forecast(pnl_data):
    """Run Prophet forecast on Net Income."""
    df = pd.DataFrame(pnl_data)
    df["Month"] = pd.to_datetime(df["Month"])
    df = df.sort_values("Month")

    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]
    model = Prophet(yearly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="MS")
    forecast = model.predict(future)

    # Plot
    plt.figure(figsize=(8, 5))
    plt.plot(df["Month"], df["NetIncome"], label="Actual Net Income", marker="o")
    plt.plot(forecast["ds"], forecast["yhat"], label="Forecast", linestyle="--", marker="x")
    plt.title("Net Income Forecast")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)

    img = BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plt.close()
    return forecast, base64.b64encode(img.getvalue()).decode()

@app.route("/")
def index():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    auth_url = (
        f"https://appcenter.intuit.com/connect/oauth2?"
        f"client_id={CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting"
        f"&redirect_uri={REDIRECT_URI}&state=secureRandomState"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl():
    return jsonify({"data": fetch_pnl_report()})

@app.route("/forecast")
def forecast():
    pnl_data = fetch_pnl_report()
    if not pnl_data:
        return "No P&L data available", 500
    forecast_df, chart = build_forecast(pnl_data)
    avg_net_income = forecast_df.tail(3)["yhat"].mean()

    html = f"""
    <html>
    <body>
        <h1 style="font-family: Arial, sans-serif;">Financial Forecast Summary</h1>
        <h2 style="font-family: Arial, sans-serif;">Average Net Income (Next 3 Months): ${avg_net_income:,.2f}</h2>
        <img src="data:image/png;base64,{chart}" alt="Forecast Chart" style="max-width:100%; height:auto;">
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
