import os
import requests
import pandas as pd
from datetime import datetime
from flask import Flask, jsonify, render_template_string, redirect, request
from prophet import Prophet
import matplotlib.pyplot as plt
import io
import base64

# Environment variables
QB_CLIENT_ID = os.getenv("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
QB_REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
QB_REALM_ID = os.getenv("QB_REALM_ID")
QB_ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "production")
REDIRECT_URI = os.getenv("REDIRECT_URI")

BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# Flask app
app = Flask(__name__)

def get_access_token():
    """Refresh QuickBooks access token."""
    response = requests.post(
        TOKEN_URL,
        auth=(QB_CLIENT_ID, QB_CLIENT_SECRET),
        headers={"Accept": "application/json"},
        data={"grant_type": "refresh_token", "refresh_token": QB_REFRESH_TOKEN},
    )
    data = response.json()
    return data.get("access_token")

def fetch_pnl_report():
    """Fetch and structure P&L data (monthly)."""
    token = get_access_token()
    if not token:
        return []

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{QB_REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    raw = response.json()

    # Debugging if needed
    # print("DEBUG Raw QuickBooks P&L:", raw)

    # Handle data safely
    rows = raw.get("Rows", {}).get("Row", [])
    income = 0
    expenses = 0
    for r in rows:
        if r.get("group") == "Income":
            try:
                income = float(r["Summary"]["ColData"][1]["value"])
            except:
                income = 0
        elif r.get("group") == "Expenses":
            try:
                expenses = float(r["Summary"]["ColData"][1]["value"])
            except:
                expenses = 0

    net_income = income - expenses

    # Generate monthly buckets (backfill with zeros)
    months = pd.date_range(start=start_date, end=end_date, freq="M")
    data = []
    for month in months:
        if month.month == datetime.now().month:
            data.append({"Month": month.strftime("%b %Y"), "Revenue": income, "Expenses": expenses, "NetIncome": net_income})
        else:
            # Zero placeholder months
            data.append({"Month": month.strftime("%b %Y"), "Revenue": 0, "Expenses": 0, "NetIncome": 0, "Note": "No Data"})

    return data

def build_forecast(data):
    """Build Prophet forecast for next 3 months using Net Income."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y", errors="coerce")
    df.fillna(0, inplace=True)

    prophet_df = df[["Month", "NetIncome"]].rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)

    return forecast[["ds", "yhat"]].tail(3).to_dict(orient="records")

def generate_chart(data, forecast):
    """Create a line chart for Net Income and Forecast."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y", errors="coerce")

    forecast_df = pd.DataFrame(forecast)
    forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])

    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["NetIncome"], marker="o", label="Actual Net Income")
    plt.plot(forecast_df["ds"], forecast_df["yhat"], marker="x", linestyle="--", label="Forecast", color="orange")
    plt.title("Net Income Forecast")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)

    # Encode image for HTML
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return encoded

@app.route("/")
def home():
    return "Clariqor App Running"

@app.route("/pnl")
def pnl():
    return jsonify({"data": fetch_pnl_report()})

@app.route("/forecast")
def forecast():
    data = fetch_pnl_report()
    forecast_data = build_forecast(data)
    chart = generate_chart(data, forecast_data)
    avg_net_income = sum([f["yhat"] for f in forecast_data]) / len(forecast_data)

    html = f"""
    <h1 style="font-family: Arial; font-weight: bold;">Financial Forecast Summary</h1>
    <p style="font-size: 18px;"><b>Average Net Income (Next 3 Months):</b> ${avg_net_income:,.2f}</p>
    <img src="data:image/png;base64,{chart}" alt="Net Income Forecast" style="max-width:100%;">
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
