import os
import json
from flask import Flask, jsonify, redirect, request, render_template_string
import requests
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from datetime import datetime
from dateutil.relativedelta import relativedelta

app = Flask(__name__)

# Environment variables
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("QB_REALM_ID")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://quickbooks-app-3.onrender.com/callback")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


def get_access_token():
    """Exchange refresh token for access token."""
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    response = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_pnl_report():
    """Fetch Profit & Loss report and build monthly records (with backfill)."""
    token = get_access_token()
    if not token:
        return []

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}&summarize_column_by=Month"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        return []

    raw_data = response.json()
    rows = raw_data.get("Rows", {}).get("Row", [])
    records = {}

    # Parse QuickBooks rows
    for row in rows:
        if row.get("type") == "Section" and row.get("group") in ["Income", "Expenses"]:
            group = row["group"]
            for sub in row.get("Rows", {}).get("Row", []):
                if "ColData" in sub:
                    amount = float(sub["ColData"][1].get("value", 0) or 0)
                    # Assume this entire block is for the current period (QuickBooks returns YTD totals)
                    month = datetime.now().strftime("%b %Y")
                    if month not in records:
                        records[month] = {"Month": month, "Revenue": 0, "Expenses": 0, "NetIncome": 0}
                    if group == "Income":
                        records[month]["Revenue"] += amount
                    elif group == "Expenses":
                        records[month]["Expenses"] += amount

    # Compute Net Income for each month
    for month, vals in records.items():
        vals["NetIncome"] = vals["Revenue"] - vals["Expenses"]

    # Backfill months from Jan to current with zeros where missing
    months = pd.date_range(start=f"{datetime.now().year}-01-01", end=datetime.now(), freq="MS")
    for m in months:
        label = m.strftime("%b %Y")
        if label not in records:
            records[label] = {"Month": label, "Revenue": 0, "Expenses": 0, "NetIncome": 0}

    return list(records.values())


def build_forecast(data):
    """Run Prophet forecast on Net Income."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y")
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]
    if len(prophet_df.dropna()) < 2:
        return None  # Not enough data to forecast

    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    return forecast[["ds", "yhat"]].tail(3).to_dict(orient="records")


def plot_forecast(data, forecast):
    """Generate a combined actual vs forecast chart."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y")
    forecast_df = pd.DataFrame(forecast)
    plt.figure(figsize=(8, 4))
    plt.plot(df["Month"], df["NetIncome"], marker="o", label="Actual Net Income")
    plt.plot(forecast_df["ds"], forecast_df["yhat"], marker="x", linestyle="--", label="Forecast")
    plt.title("Net Income Forecast")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)

    # Convert plot to base64 for embedding
    buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    img_b64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close()
    return f'<img src="data:image/png;base64,{img_b64}" alt="Forecast Chart">'


@app.route("/")
def home():
    return "QuickBooks App Running!"


@app.route("/connect")
def connect():
    """OAuth redirect to QuickBooks."""
    auth_url = (
        "https://appcenter.intuit.com/connect/oauth2"
        f"?client_id={CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting"
        f"&redirect_uri={REDIRECT_URI}&state=secureRandomState"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    return "QuickBooks connected successfully!"


@app.route("/pnl")
def pnl():
    data = fetch_pnl_report()
    return jsonify({"data": data})


@app.route("/forecast")
def forecast():
    data = fetch_pnl_report()
    forecast_data = build_forecast(data)
    if not forecast_data:
        return "Not enough data to build a forecast."
    chart = plot_forecast(data, forecast_data)
    avg_net_income = sum(f["yhat"] for f in forecast_data) / len(forecast_data)
    return render_template_string(f"""
        <h1>Financial Forecast Summary</h1>
        <p><b>Average Net Income (Next 3 Months):</b> ${avg_net_income:,.2f}</p>
        {chart}
    """)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
