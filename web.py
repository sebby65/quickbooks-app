import os
import io
import json
import base64
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from flask import Flask, jsonify, send_file, render_template
from prophet import Prophet
from fpdf import FPDF

from fetch_qb_data import get_access_token, fetch_profit_and_loss
from email_utils import send_email

app = Flask(__name__)

# Branding
CLARIQOR_LOGO = "https://via.placeholder.com/150x50?text=Clariqor"  # Placeholder logo
REPORT_TITLE = "Clariqor Financial Forecast"

# ----------------------------
# DATA FETCH + PROCESSING
# ----------------------------
def get_pnl_data():
    token = get_access_token()
    if not token:
        return pd.DataFrame()

    raw = fetch_profit_and_loss(token)
    # Parse QuickBooks report
    income = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Income"), 0))
    expenses = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Expenses"), 0))
    net = income - expenses

    today = datetime.today()
    df = pd.DataFrame([{
        "Month": today.replace(day=1),
        "Revenue": income,
        "Expenses": expenses,
        "NetIncome": net
    }])

    # Backfill missing months
    start_date = today.replace(month=1, day=1)
    months = pd.date_range(start=start_date, end=today, freq="MS")
    df = df.set_index("Month").reindex(months, fill_value=0).reset_index().rename(columns={"index": "Month"})
    return df

# ----------------------------
# FORECAST GENERATION
# ----------------------------
def generate_forecast(df):
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=6, freq="MS")
    forecast = model.predict(future)

    # Build display frame
    forecast_df = pd.DataFrame({
        "Month": forecast["ds"],
        "PredictedNetIncome": forecast["yhat"].round(2)
    })
    return forecast_df

# ----------------------------
# VISUALIZATION (Chart)
# ----------------------------
def build_chart(df, forecast_df):
    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["Revenue"], label="Revenue", marker="o")
    plt.plot(df["Month"], df["Expenses"], label="Expenses", marker="o")
    plt.plot(forecast_df["Month"], forecast_df["PredictedNetIncome"], label="Forecasted Net Income", linestyle="--")
    plt.title("Monthly Financial Overview")
    plt.xlabel("Month")
    plt.ylabel("USD")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    plt.close()
    return img

# ----------------------------
# PDF REPORT GENERATION
# ----------------------------
def build_pdf(df, forecast_df, chart_img):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)

    # Title + Branding
    pdf.cell(0, 10, REPORT_TITLE, ln=True, align="C")
    pdf.image(CLARIQOR_LOGO, x=150, y=10, w=40)

    # Summary Insights
    revenue = df["Revenue"].sum()
    expenses = df["Expenses"].sum()
    net = revenue - expenses
    growth = forecast_df["PredictedNetIncome"].iloc[-1] - df["NetIncome"].iloc[-1]

    pdf.set_font("Arial", "", 12)
    pdf.ln(20)
    pdf.multi_cell(0, 8, f"Total Revenue: ${revenue:,.0f}\n"
                         f"Total Expenses: ${expenses:,.0f}\n"
                         f"Net Income: ${net:,.0f}\n"
                         f"Projected Growth (6 months): ${growth:,.0f}")

    # Chart
    img_bytes = chart_img.read()
    chart_path = "chart.png"
    with open(chart_path, "wb") as f:
        f.write(img_bytes)
    pdf.image(chart_path, x=10, y=100, w=190)

    # Save PDF
    pdf_path = "Clariqor_Financial_Report.pdf"
    pdf.output(pdf_path)
    return pdf_path

# ----------------------------
# ROUTES
# ----------------------------
@app.route("/")
def home():
    return "Clariqor Financial Forecast App"

@app.route("/pnl")
def pnl():
    df = get_pnl_data()
    return jsonify(df.to_dict(orient="records"))

@app.route("/forecast")
def forecast():
    df = get_pnl_data()
    forecast_df = generate_forecast(df)
    chart_img = build_chart(df, forecast_df)
    pdf_path = build_pdf(df, forecast_df, chart_img)

    # Email PDF (to email in .env)
    recipient = os.getenv("EMAIL_USER")
    send_email(recipient, "Your Clariqor Financial Forecast", "Attached is your forecast report.", pdf_path)

    # Return HTML page with download
    return f"""
    <html>
        <body style="font-family: Arial; text-align: center;">
            <h1>Clariqor Forecast</h1>
            <p>Your report has been generated and emailed to {recipient}.</p>
            <a href="/download" style="font-size: 18px;">Download PDF Report</a>
        </body>
    </html>
    """

@app.route("/download")
def download_pdf():
    return send_file("Clariqor_Financial_Report.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
