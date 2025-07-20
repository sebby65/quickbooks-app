import os
import io
import base64
from datetime import datetime
import requests
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, jsonify, send_file, render_template_string
from fpdf import FPDF
from prophet import Prophet
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("REALM_ID")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

app = Flask(__name__)

# -----------------------
# TOKEN + DATA HELPERS
# -----------------------

def get_access_token():
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }
    try:
        response = requests.post(TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception:
        return None

def fetch_qb_pnl():
    """Fetch Profit & Loss data from QuickBooks, or return [] if not available."""
    token = get_access_token()
    if not token or not REALM_ID:
        return []

    today = datetime.today().strftime("%Y-%m-%d")
    start = f"{datetime.today().year}-01-01"
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start}&end_date={today}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return []
        raw = res.json()

        # Parse values from QuickBooks JSON (safely)
        income = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Income"), 0))
        expenses = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "Expenses"), 0))
        net = float(next((r["Summary"]["ColData"][1]["value"] for r in raw["Rows"]["Row"] if r.get("group") == "NetIncome"), 0))

        month_label = datetime.today().strftime("%b %Y")
        return [{"Month": month_label, "Revenue": round(income, 2), "Expenses": round(expenses, 2), "NetIncome": round(net, 2)}]
    except Exception:
        return []

def get_pnl_data():
    """Fetch real QuickBooks P&L, fallback to mock data if empty."""
    data = fetch_qb_pnl()
    if not data:
        # Mock fallback data
        data = [
            {"Month": "Jan 2025", "Revenue": 90000, "Expenses": 30000, "NetIncome": 60000},
            {"Month": "Feb 2025", "Revenue": 105000, "Expenses": 35000, "NetIncome": 70000},
            {"Month": "Mar 2025", "Revenue": 95000, "Expenses": 40000, "NetIncome": 55000},
        ]
    return pd.DataFrame(data)

# -----------------------
# FORECAST + INSIGHTS
# -----------------------

def forecast_net_income(df):
    df["Month"] = pd.to_datetime(df["Month"], errors="coerce")
    df = df.dropna(subset=["Month"])  # avoid NaT
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    return forecast

def generate_insight(df):
    if len(df) < 2:
        return "Insufficient data for trend analysis."
    change = df["NetIncome"].iloc[-1] - df["NetIncome"].iloc[-2]
    pct = (change / max(df["NetIncome"].iloc[-2], 1)) * 100
    if change > 0:
        return f"Net Income increased by {pct:.1f}% compared to last month."
    elif change < 0:
        return f"Net Income decreased by {abs(pct):.1f}% compared to last month."
    else:
        return "Net Income remained flat compared to last month."

def plot_chart(df):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df["Month"], df["NetIncome"], marker="o", label="Net Income")
    ax.set_title("Net Income Over Time")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net Income ($)")
    ax.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# -----------------------
# ROUTES
# -----------------------

@app.route("/pnl")
def pnl():
    df = get_pnl_data()
    return jsonify(df.to_dict(orient="records"))

@app.route("/forecast")
def forecast_route():
    df = get_pnl_data()
    forecast = forecast_net_income(df)
    chart = plot_chart(df)
    insight = generate_insight(df)
    html = f"""
    <html>
    <head><title>Forecast Report</title></head>
    <body>
        <h2>Profit & Loss Forecast</h2>
        <p>{insight}</p>
        <img src="data:image/png;base64,{chart}" />
    </body>
    </html>
    """
    return html

@app.route("/report")
def pdf_report():
    df = get_pnl_data()
    insight = generate_insight(df)

    # Generate chart image
    chart_b64 = plot_chart(df)
    chart_data = base64.b64decode(chart_b64)
    chart_path = "chart.png"
    with open(chart_path, "wb") as f:
        f.write(chart_data)

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Financial Summary Report", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, f"Insight: {insight}")
    pdf.ln(5)
    pdf.image(chart_path, x=10, y=None, w=180)
    pdf.ln(85)

    # Table
    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 10, "Month", 1)
    pdf.cell(50, 10, "Revenue ($)", 1)
    pdf.cell(50, 10, "Expenses ($)", 1)
    pdf.cell(50, 10, "Net Income ($)", 1)
    pdf.ln()
    pdf.set_font("Arial", "", 12)
    for _, row in df.iterrows():
        pdf.cell(40, 10, str(row["Month"]), 1)
        pdf.cell(50, 10, f"{row['Revenue']:,.0f}", 1)
        pdf.cell(50, 10, f"{row['Expenses']:,.0f}", 1)
        pdf.cell(50, 10, f"{row['NetIncome']:,.0f}", 1)
        pdf.ln()

    output_path = "financial_report.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
