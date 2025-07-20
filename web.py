import os
from flask import Flask, redirect, request, jsonify
import requests
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
load_dotenv()

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
REALM_ID = os.getenv("QB_REALM_ID")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

def get_access_token():
    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    auth_header = f"{CLIENT_ID}:{CLIENT_SECRET}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic " + base64.b64encode(auth_header.encode()).decode(),
    }
    payload = f"grant_type=refresh_token&refresh_token={REFRESH_TOKEN}"
    res = requests.post(url, headers=headers, data=payload)
    res_data = res.json()
    return res_data.get("access_token")

def fetch_pnl_report():
    """Fetch Profit & Loss report and backfill missing months with 0 values."""
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
    income = float(next((r['ColData'][1]['value'] for r in raw["Rows"]["Row"] if r.get("group") == "Income"), 0))
    expenses = float(next((r['ColData'][1]['value'] for r in raw["Rows"]["Row"] if r.get("group") == "Expenses"), 0))
    net_income = float(next((r['ColData'][1]['value'] for r in raw["Rows"]["Row"] if r.get("group") == "NetIncome"), 0))

    # Backfill all months of the year so Prophet has enough data
    months = pd.date_range(start=f"{datetime.now().year}-01-01", end=datetime.now(), freq="MS")
    pnl_data = []
    for m in months:
        pnl_data.append({
            "Month": m.strftime("%b %Y"),
            "Revenue": income if m.month == datetime.now().month else 0,
            "Expenses": expenses if m.month == datetime.now().month else 0,
            "NetIncome": net_income if m.month == datetime.now().month else 0
        })
    return pnl_data

def build_forecast(pnl_data):
    df = pd.DataFrame(pnl_data)
    df["Date"] = pd.to_datetime(df["Month"])
    prophet_df = df.rename(columns={"Date": "ds", "NetIncome": "y"})[["ds", "y"]]
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    return df, forecast

def create_chart(df, forecast):
    plt.figure(figsize=(10, 6))
    plt.plot(df["Date"], df["NetIncome"], label="Actual Net Income", marker="o")
    plt.plot(forecast["ds"], forecast["yhat"], label="Forecast", linestyle="--", marker="x")
    plt.title("Net Income Forecast", fontsize=16)
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return encoded

@app.route("/")
def home():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    return redirect(f"https://appcenter.intuit.com/connect/oauth2?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=com.intuit.quickbooks.accounting&state=secureRandomState")

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
        return "No P&L data found", 404
    df, forecast = build_forecast(pnl_data)
    avg_income = forecast.tail(3)["yhat"].mean()
    chart = create_chart(df, forecast)
    return f"""
        <h1 style="font-family: Arial, sans-serif;">Financial Forecast Summary</h1>
        <h2 style="font-family: Arial, sans-serif;">Average Net Income (Next 3 Months): ${avg_income:,.2f}</h2>
        <img src="data:image/png;base64,{chart}" style="max-width:100%;border:1px solid #ddd;border-radius:8px;"/>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
