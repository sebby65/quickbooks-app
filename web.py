import os
from flask import Flask, render_template_string, redirect, request
import requests
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")

app = Flask(__name__)

# QuickBooks Token Exchange (get access token using refresh token)
def get_access_token():
    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }
    auth = (CLIENT_ID, CLIENT_SECRET)
    response = requests.post(url, headers=headers, data=data, auth=auth)
    response.raise_for_status()
    return response.json()["access_token"]

# Fetch Profit & Loss grouped by month
def fetch_pnl_report():
    token = get_access_token()
    url = f"https://quickbooks.api.intuit.com/v3/company/{REALM_ID}/reports/ProfitAndLoss"
    params = {
        "start_date": f"{datetime.now().year}-01-01",
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "accounting_method": "Accrual",
        "summarize_column_by": "Month"
    }
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

# Convert QuickBooks report JSON to DataFrame
def report_to_df(report):
    rows = report.get("Rows", {}).get("Row", [])
    months = []
    revenues = []
    expenses = []
    net_incomes = []

    # QuickBooks monthly totals are in Columns section
    for row in rows:
        if row.get("Header") and row["Header"]["ColData"][0]["value"] == "Total Income":
            for col in row["Summary"]["ColData"]:
                revenues.append(float(col.get("value", 0)))
        elif row.get("Header") and row["Header"]["ColData"][0]["value"] == "Total Expenses":
            for col in row["Summary"]["ColData"]:
                expenses.append(float(col.get("value", 0)))
        elif row.get("Header") and row["Header"]["ColData"][0]["value"] == "Net Operating Income":
            for col in row["Summary"]["ColData"]:
                net_incomes.append(float(col.get("value", 0)))

    # Extract month names from Columns header
    cols = report.get("Columns", {}).get("Column", [])
    for col in cols:
        if col.get("ColType") == "Month":
            months.append(col.get("ColTitle", ""))

    # Build DataFrame
    df = pd.DataFrame({
        "Month": months,
        "Revenue": revenues,
        "Expenses": expenses,
        "NetIncome": net_incomes
    })
    return df

# Forecast Net Income using Prophet
def forecast_net_income(df):
    prophet_df = df[["Month", "NetIncome"]].copy()
    prophet_df["Month"] = pd.to_datetime(prophet_df["Month"])
    prophet_df.rename(columns={"Month": "ds", "NetIncome": "y"}, inplace=True)

    model = Prophet()
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=3, freq="ME")  # 3-month forecast
    forecast = model.predict(future)

    forecast_df = forecast[["ds", "yhat"]].tail(3)
    forecast_df.rename(columns={"ds": "Month", "yhat": "ForecastedNetIncome"}, inplace=True)
    return forecast_df

# Build Plotly chart
def build_forecast_chart(df, forecast_df):
    fig = go.Figure()

    # Actual Net Income
    fig.add_trace(go.Scatter(x=df["Month"], y=df["NetIncome"], mode="lines+markers", name="Actual Net Income"))

    # Forecasted Net Income
    fig.add_trace(go.Scatter(x=forecast_df["Month"], y=forecast_df["ForecastedNetIncome"], mode="lines+markers",
                             name="Forecasted Net Income"))

    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD")
    return fig.to_html(full_html=False)

# Flask Routes
@app.route("/")
def index():
    return render_template_string("""
        <h1>Financial Forecast Dashboard</h1>
        <a href="/auth">Authorize QuickBooks</a><br><br>
        <a href="/pnl">View P&L</a><br>
        <a href="/forecast">View Forecast</a>
    """)

@app.route("/auth")
def auth():
    return "QuickBooks is already connected. You can now view /pnl or /forecast."

@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    df = report_to_df(report)
    return df.to_json(orient="records")

@app.route("/forecast")
def forecast_route():
    report = fetch_pnl_report()
    df = report_to_df(report)
    forecast_df = forecast_net_income(df)
    chart_html = build_forecast_chart(df, forecast_df)
    return render_template_string(f"""
        <h1>Financial Forecast Summary</h1>
        <p>Last Month: Revenue ${df['Revenue'].iloc[-1]:,.2f}, 
        Expenses ${df['Expenses'].iloc[-1]:,.2f}, 
        Net Income ${df['NetIncome'].iloc[-1]:,.2f}</p>
        <p>Next 3 Months Forecast Avg Net Income: ${forecast_df['ForecastedNetIncome'].mean():,.2f}</p>
        {chart_html}
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
