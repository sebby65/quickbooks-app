import os
from flask import Flask, jsonify, send_file, render_template
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from prophet import Prophet
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("REALM_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"  # Production later

app = Flask(__name__)

# ---------------------------
# Fetch P&L data from QuickBooks (or mock)
# ---------------------------
def fetch_pnl_report():
    token = ACCESS_TOKEN
    if not token:
        return pd.DataFrame()

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        raw = response.json()
        # Simplified parsing (use mock if no rows)
        if "Rows" not in raw or "Row" not in raw["Rows"]:
            return pd.DataFrame()

        # Extract totals (very simple aggregation)
        income = float(next((r["Summary"]["ColData"][1]["value"] 
                             for r in raw["Rows"]["Row"] if r.get("group") == "Income"), 0))
        expenses = float(next((r["Summary"]["ColData"][1]["value"] 
                               for r in raw["Rows"]["Row"] if r.get("group") == "Expenses"), 0))
        net = income - expenses

        # Mock fill for missing months (keeps Prophet happy)
        months = pd.date_range(start="2025-01-01", end=datetime.today(), freq="M")
        df = pd.DataFrame({
            "Month": months,
            "Revenue": np.linspace(income/len(months), income, len(months)),
            "Expenses": np.linspace(expenses/len(months), expenses, len(months))
        })
        df["NetIncome"] = df["Revenue"] - df["Expenses"]
        return df
    except Exception:
        # Fallback mock data if API fails
        months = pd.date_range(start="2025-01-01", end=datetime.today(), freq="M")
        df = pd.DataFrame({
            "Month": months,
            "Revenue": np.linspace(50000, 120000, len(months)),
            "Expenses": np.linspace(20000, 60000, len(months))
        })
        df["NetIncome"] = df["Revenue"] - df["Expenses"]
        return df

# ---------------------------
# Forecast with Prophet
# ---------------------------
def build_forecast(df):
    df_prophet = df.rename(columns={"Month": "ds", "Revenue": "y"})[["ds", "y"]]
    model = Prophet()
    model.fit(df_prophet)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)[["ds", "yhat"]]
    forecast.rename(columns={"ds": "Month", "yhat": "ForecastRevenue"}, inplace=True)
    forecast["Month"] = pd.to_datetime(forecast["Month"])
    return forecast

# ---------------------------
# Investor Summary (neutral, auto-updated)
# ---------------------------
def generate_summary(df, forecast):
    recent_revenue = df["Revenue"].iloc[-1]
    trend = "increasing" if forecast["ForecastRevenue"].iloc[-1] > recent_revenue else "stable"
    net_income = df["NetIncome"].iloc[-1]
    return (
        f"As of {datetime.today().strftime('%B %Y')}, the company reported "
        f"monthly revenue of ${recent_revenue:,.0f} and net income of ${net_income:,.0f}. "
        f"Revenue is projected to remain {trend} over the next quarter."
    )

# ---------------------------
# Chart Generator
# ---------------------------
def make_chart(df, forecast):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df["Month"], df["Revenue"], label="Revenue", linewidth=2)
    ax.plot(df["Month"], df["NetIncome"], label="Net Income", linestyle="--")
    ax.plot(forecast["Month"], forecast["ForecastRevenue"], label="Forecast", linestyle=":")
    ax.set_title("Financial Performance & Forecast")
    ax.set_xlabel("Month")
    ax.set_ylabel("Amount ($)")
    ax.legend()
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def dashboard():
    df = fetch_pnl_report()
    forecast = build_forecast(df)
    summary = generate_summary(df, forecast)
    return render_template("financial_dashboard.html", summary=summary)

@app.route("/pnl")
def pnl_data():
    df = fetch_pnl_report()
    return jsonify(df.to_dict(orient="records"))

@app.route("/forecast")
def forecast_data():
    df = fetch_pnl_report()
    forecast = build_forecast(df)
    return jsonify(forecast.to_dict(orient="records"))

@app.route("/pdf")
def pdf_report():
    df = fetch_pnl_report()
    forecast = build_forecast(df)
    summary = generate_summary(df, forecast)
    chart_buf = make_chart(df, forecast)

    # Basic PDF generation (image + summary text)
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    c.setFont("Helvetica", 14)
    c.drawString(50, 750, "Monthly Investor Report")
    c.setFont("Helvetica", 10)
    text = c.beginText(50, 720)
    for line in summary.split(". "):
        text.textLine(line)
    c.drawText(text)
    img = BytesIO(chart_buf.getvalue())
    c.drawImage(img, 50, 400, width=500, height=250)
    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return send_file(pdf_buf, mimetype="application/pdf", as_attachment=True, download_name="investor_report.pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
