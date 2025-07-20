import os
from flask import Flask, render_template_string, redirect, request
import requests
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
app = Flask(__name__)

# --- Save environment updates ---
def save_env_var(key, value):
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()
    with open(env_file, "w") as f:
        updated = False
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"{key}={value}\n")

# --- Token exchange with auto-refresh ---
def get_access_token():
    global REFRESH_TOKEN
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    auth = (CLIENT_ID, CLIENT_SECRET)
    response = requests.post(TOKEN_URL, headers=headers, data=data, auth=auth)

    if response.status_code != 200:
        raise Exception(f"QuickBooks token error: {response.text}")

    token_data = response.json()
    if "refresh_token" in token_data:
        REFRESH_TOKEN = token_data["refresh_token"]
        save_env_var("QB_REFRESH_TOKEN", REFRESH_TOKEN)
    return token_data.get("access_token")

# --- Fetch P&L grouped by month (with retry and fallback) ---
def fetch_pnl_report():
    try:
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

        # Retry if token expired (401/400)
        if response.status_code in (400, 401):
            token = get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=headers, params=params)

        response.raise_for_status()
        report = response.json()

        # If QuickBooks has no data, use fallback
        if not report.get("Rows") or not report["Rows"].get("Row"):
            return None

        return report

    except Exception as e:
        print(f"QuickBooks fetch failed: {e}")
        return None

# --- Convert QuickBooks or mock data to DataFrame ---
def report_to_df(report=None):
    if report is None:
        # Fallback mock data
        months = pd.date_range(f"{datetime.now().year}-01-01", periods=6, freq="ME").strftime("%b %Y")
        revenue = [90000, 105000, 98000, 110000, 120000, 115000]
        expenses = [30000, 35000, 32000, 36000, 38000, 34000]
        net_income = [r - e for r, e in zip(revenue, expenses)]
        return pd.DataFrame({"Month": months, "Revenue": revenue, "Expenses": expenses, "NetIncome": net_income})

    # Parse actual QuickBooks report
    cols = [c.get("ColTitle", "") for c in report.get("Columns", {}).get("Column", []) if c.get("ColType") == "Month"]
    totals = {"Revenue": [], "Expenses": [], "NetIncome": []}

    for row in report.get("Rows", {}).get("Row", []):
        header = row.get("Header", {}).get("ColData", [{}])[0].get("value", "").lower()
        values = [float(c.get("value", "0").replace(",", "") or 0) for c in row.get("Summary", {}).get("ColData", [])]
        if "income" in header and "total" in header:
            totals["Revenue"] = values
        elif "expense" in header:
            totals["Expenses"] = values
        elif "net operating income" in header or "net income" in header:
            totals["NetIncome"] = values

    # Compute Net Income if QuickBooks didn't give it
    if not totals["NetIncome"] and totals["Revenue"] and totals["Expenses"]:
        totals["NetIncome"] = [r - e for r, e in zip(totals["Revenue"], totals["Expenses"])]

    return pd.DataFrame({
        "Month": cols,
        "Revenue": totals.get("Revenue", [0] * len(cols)),
        "Expenses": totals.get("Expenses", [0] * len(cols)),
        "NetIncome": totals.get("NetIncome", [0] * len(cols))
    })

# --- Forecast Net Income ---
def forecast_net_income(df):
    df["Month"] = pd.to_datetime(df["Month"])
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="ME")
    forecast = model.predict(future)
    forecast_df = forecast[["ds", "yhat"]].tail(3)
    forecast_df.rename(columns={"ds": "Month", "yhat": "ForecastedNetIncome"}, inplace=True)
    return forecast_df

# --- Chart Builder ---
def build_chart(df, forecast_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Month"], y=df["NetIncome"], mode="lines+markers", name="Actual Net Income"))
    fig.add_trace(go.Scatter(x=forecast_df["Month"], y=forecast_df["ForecastedNetIncome"],
                             mode="lines+markers", name="Forecasted Net Income"))
    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD")
    return fig.to_html(full_html=False)

# --- Routes ---
@app.route("/")
def index():
    return render_template_string("""
        <h1>Financial Forecast Dashboard</h1>
        <a href="/pnl">View P&L</a><br>
        <a href="/forecast">View Forecast</a>
    """)

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
    chart = build_chart(df, forecast_df)
    return render_template_string(f"""
        <h1>Financial Forecast Summary</h1>
        <p>Last Month: Revenue ${df['Revenue'].iloc[-1]:,.2f}, Expenses ${df['Expenses'].iloc[-1]:,.2f}, Net Income ${df['NetIncome'].iloc[-1]:,.2f}</p>
        <p>Next 3-Month Avg Forecasted Net Income: ${forecast_df['ForecastedNetIncome'].mean():,.2f}</p>
        {chart}
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
