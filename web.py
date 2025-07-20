import os
import json
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
from flask import Flask, redirect, render_template_string, request
from prophet import Prophet

# Load environment variables
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
QB_REFRESH_TOKEN = os.environ.get("QB_REFRESH_TOKEN")
QB_REALM_ID = os.environ.get("QB_REALM_ID")
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

def get_access_token():
    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    auth = (QB_CLIENT_ID, QB_CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": QB_REFRESH_TOKEN}
    response = requests.post(url, headers=headers, data=data, auth=auth)
    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    print("DEBUG Token Error:", response.text)
    return None

def fetch_pnl_report():
    token = get_access_token()
    if not token:
        return []
    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{QB_REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        return []
    data = response.json()
    income = float(data["Rows"]["Row"][0]["Rows"]["Row"][0]["ColData"][1]["value"])
    expenses = float(data["Rows"]["Row"][2]["Summary"]["ColData"][1]["value"])
    net_income = float(data["Rows"]["Row"][4]["Summary"]["ColData"][1]["value"])
    return [{"Month": datetime.now().strftime("%b %Y"), "Revenue": income, "Expenses": expenses, "NetIncome": net_income}]

def build_forecast(data):
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], errors="coerce")
    prophet_df = pd.DataFrame({"ds": df["Month"], "y": df["NetIncome"]})
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    return forecast[["ds", "yhat"]].tail(3).to_dict(orient="records")

def build_chart(data, forecast):
    df_actual = pd.DataFrame(data)
    df_actual["Month"] = pd.to_datetime(df_actual["Month"], errors="coerce")
    df_forecast = pd.DataFrame(forecast)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_actual["Month"], y=df_actual["NetIncome"], mode="lines+markers", name="Actual Net Income"))
    fig.add_trace(go.Scatter(x=df_forecast["ds"], y=df_forecast["yhat"], mode="lines+markers", name="Forecast Net Income"))
    fig.update_layout(title="QuickBooks P&L Forecast", xaxis_title="Month", yaxis_title="USD", template="plotly_white")
    return fig.to_html(full_html=False)

app = Flask(__name__)

@app.route("/")
def index():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    auth_url = (
        "https://appcenter.intuit.com/connect/oauth2"
        f"?client_id={QB_CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting"
        f"&redirect_uri={REDIRECT_URI}&state=secureRandomState"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl():
    data = fetch_pnl_report()
    return json.dumps({"data": data})

@app.route("/forecast")
def forecast():
    data = fetch_pnl_report()
    forecast_data = build_forecast(data)
    chart_html = build_chart(data, forecast_data)
    avg_net_income = sum(item["yhat"] for item in forecast_data) / len(forecast_data)
    html = f"""
    <h1>Financial Forecast Summary</h1>
    <p><b>Average Net Income (Next 3 Months):</b> ${avg_net_income:,.2f}</p>
    {chart_html}
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
