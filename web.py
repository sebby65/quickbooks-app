import os
import requests
from flask import Flask, jsonify, redirect, render_template_string, request
from datetime import datetime
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import io, base64

# Flask app
app = Flask(__name__)
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REALM_ID = os.getenv("QB_REALM_ID")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
BASE_URL = f"https://quickbooks.api.intuit.com/v3/company/{REALM_ID}"
REDIRECT_URI = os.getenv("REDIRECT_URI")
ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "production")

token_cache = {"access_token": None, "expires_at": None}

# === OAuth: Fetch Access Token ===
def get_access_token():
    global token_cache
    if token_cache["access_token"] and datetime.utcnow() < token_cache["expires_at"]:
        return token_cache["access_token"]

    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    resp = requests.post(url, headers=headers, auth=auth, data=data)
    if resp.status_code != 200:
        print("Token Refresh Failed:", resp.text)
        return None

    tokens = resp.json()
    token_cache["access_token"] = tokens["access_token"]
    token_cache["expires_at"] = datetime.utcnow() + pd.Timedelta(seconds=tokens["expires_in"] - 60)
    return token_cache["access_token"]

# === Helper: Fetch QuickBooks Data ===
def qb_query(query):
    token = get_access_token()
    if not token: return []
    url = f"{BASE_URL}/query?query={query}&minorversion=65"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("QB Query Failed:", resp.text)
        return []
    return resp.json().get("QueryResponse", {})

def aggregate_monthly_data():
    """Fetch Revenue & Expenses per month from Invoices and Purchases"""
    try:
        invoices = qb_query("SELECT * FROM Invoice")
        purchases = qb_query("SELECT * FROM Purchase")

        revenue_by_month, expense_by_month = {}, {}
        date_format = "%Y-%m-%d"

        # Aggregate Revenue
        for inv in invoices.get("Invoice", []):
            date = datetime.strptime(inv["TxnDate"], date_format)
            month = date.strftime("%b %Y")
            amt = float(inv.get("TotalAmt", 0))
            revenue_by_month[month] = revenue_by_month.get(month, 0) + amt

        # Aggregate Expenses
        for pur in purchases.get("Purchase", []):
            date = datetime.strptime(pur["TxnDate"], date_format)
            month = date.strftime("%b %Y")
            amt = float(pur.get("TotalAmt", 0))
            expense_by_month[month] = expense_by_month.get(month, 0) + amt

        # Merge
        all_months = sorted(set(revenue_by_month.keys()) | set(expense_by_month.keys()))
        results = []
        for m in all_months:
            rev = revenue_by_month.get(m, 0)
            exp = expense_by_month.get(m, 0)
            results.append({"Month": m, "Revenue": rev, "Expenses": exp, "NetIncome": rev - exp})

        return results

    except Exception as e:
        print("Transaction fetch failed, falling back to P&L:", e)
        return fallback_pnl_summary()

def fallback_pnl_summary():
    """Fallback: Use Profit & Loss API if invoice/purchase query fails"""
    token = get_access_token()
    if not token: return []
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/reports/ProfitAndLoss?start_date={datetime.now().year}-01-01&end_date={today}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("Fallback P&L failed:", resp.text)
        return []

    raw = resp.json()
    income = float(next((r['ColData'][1]['value'] for r in raw.get("Rows", {}).get("Row", []) if r.get("group") == "Income"), 0))
    expenses = float(next((r['ColData'][1]['value'] for r in raw.get("Rows", {}).get("Row", []) if r.get("group") == "Expenses"), 0))
    net = income - expenses
    month = datetime.now().strftime("%b %Y")

    return [{"Month": month, "Revenue": income, "Expenses": expenses, "NetIncome": net}]

# === Forecasting ===
def build_forecast(data):
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y", errors="coerce")
    df.sort_values("Month", inplace=True)

    # Backfill missing months
    all_months = pd.date_range(df["Month"].min(), df["Month"].max(), freq="MS")
    df = df.set_index("Month").reindex(all_months).fillna(0).rename_axis("Month").reset_index()

    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="MS")
    forecast = model.predict(future)

    # Chart
    plt.figure(figsize=(8, 5))
    plt.plot(df["Month"], df["NetIncome"], label="Actual Net Income", marker="o")
    plt.plot(forecast["ds"], forecast["yhat"], label="Forecast", linestyle="--", marker="x")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.title("Net Income Forecast")
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.read()).decode("utf-8")

    avg_next_3 = forecast.tail(3)["yhat"].mean()
    return chart_base64, avg_next_3

# === Routes ===
@app.route("/")
def home():
    return "QuickBooks Connected!"

@app.route("/connect")
def connect():
    return redirect(f"https://appcenter.intuit.com/connect/oauth2?client_id={CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting&redirect_uri={REDIRECT_URI}&state=secureRandomState")

@app.route("/callback")
def callback():
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl():
    return jsonify({"data": aggregate_monthly_data()})

@app.route("/forecast")
def forecast():
    data = aggregate_monthly_data()
    if not data: return "No financial data available."
    chart, avg_income = build_forecast(data)

    html = f"""
    <h1 style="font-family: Arial; font-size: 28px;">Financial Forecast Summary</h1>
    <h2 style="font-family: Arial; font-size: 18px;">
        Average Net Income (Next 3 Months): ${avg_income:,.2f}
    </h2>
    <img src="data:image/png;base64,{chart}" style="max-width: 90%; height: auto;">
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
