import os
import json
import requests
import pandas as pd
from flask import Flask, jsonify, send_file, render_template_string, redirect
from prophet import Prophet
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
from io import BytesIO
from matplotlib.backends.backend_pdf import PdfPages

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("QB_REALM_ID")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
ACCESS_TOKEN = None  # Cached at runtime

app = Flask(__name__)

# ---- Helper: Refresh and Fetch Data ----
def get_access_token():
    global ACCESS_TOKEN
    if ACCESS_TOKEN:
        return ACCESS_TOKEN
    token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    refresh_token = os.getenv("QB_REFRESH_TOKEN")
    auth = (CLIENT_ID, CLIENT_SECRET)
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    res = requests.post(token_url, auth=auth, data=data)
    if res.status_code == 200:
        ACCESS_TOKEN = res.json()["access_token"]
        return ACCESS_TOKEN
    return None

def fetch_pnl_report():
    token = get_access_token()
    if not token:
        return []
    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return []
    raw = res.json()
    # Extract income/expenses
    income = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Income"), 0))
    expenses = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Expenses"), 0))
    net_income = income - expenses
    # Build dataframe (assume single-month snapshot for demo)
    df = pd.DataFrame([{
        "Month": datetime.now().strftime("%Y-%m"),
        "Revenue": round(income, 2),
        "Expenses": round(expenses, 2),
        "NetIncome": round(net_income, 2)
    }])
    return df

# ---- Forecast Logic ----
def build_forecast(df):
    # Backfill missing months with zeros for smoother chart
    start = pd.to_datetime(f"{datetime.now().year}-01-01")
    end = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
    all_months = pd.date_range(start=start, end=end, freq="MS")
    df["Month"] = pd.to_datetime(df["Month"])
    df = df.set_index("Month").reindex(all_months, fill_value=0).rename_axis("Month").reset_index()

    # Prophet forecast
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]
    model = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="MS")
    forecast = model.predict(future)

    # Chart
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["Month"], df["NetIncome"], label="Actual", marker="o")
    ax.plot(forecast["ds"], forecast["yhat"], label="Forecast", linestyle="--")
    ax.fill_between(forecast["ds"], forecast["yhat_lower"], forecast["yhat_upper"], color="gray", alpha=0.3)
    ax.set_title("Net Income Forecast")
    ax.set_ylabel("Net Income")
    ax.legend()
    fig.tight_layout()
    return fig, forecast

# ---- Routes ----
@app.route("/")
def home():
    return "<h3>Visit <a href='/forecast'>/forecast</a> for live report.</h3>"

@app.route("/forecast")
def forecast():
    df = fetch_pnl_report()
    if df.empty:
        return "<h4>No P&L data available. <a href='/connect'>Reconnect to QuickBooks</a></h4>"

    fig, forecast = build_forecast(df)
    # Summary text
    last_month = df.iloc[-1]
    summary = f"""
    <p><b>Latest Month:</b> {last_month['Month'].strftime('%B %Y')}<br>
    <b>Revenue:</b> ${last_month['Revenue']:,.0f}<br>
    <b>Expenses:</b> ${last_month['Expenses']:,.0f}<br>
    <b>Net Income:</b> ${last_month['NetIncome']:,.0f}</p>
    """

    # Save chart for PDF
    img_bytes = BytesIO()
    fig.savefig(img_bytes, format="png")
    img_bytes.seek(0)

    html = f"""
    <h2>QuickBooks Financial Forecast</h2>
    {summary}
    <img src="data:image/png;base64,{img_bytes.getvalue().hex()}" style="max-width:100%;"><br>
    <a href='/pdf'>Download PDF</a> | <a href='/connect'>Reconnect QuickBooks</a>
    """
    return render_template_string(html)

@app.route("/pdf")
def download_pdf():
    df = fetch_pnl_report()
    fig, _ = build_forecast(df)
    pdf_bytes = BytesIO()
    with PdfPages(pdf_bytes) as pdf:
        pdf.savefig(fig)
    pdf_bytes.seek(0)
    return send_file(pdf_bytes, mimetype="application/pdf", as_attachment=True, download_name="financial_report.pdf")

@app.route("/connect")
def reconnect():
    return "<h4>QuickBooks connection refreshed (simulated). Go to <a href='/forecast'>/forecast</a>.</h4>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
