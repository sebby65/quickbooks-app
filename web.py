import os
import json
import requests
from flask import Flask, redirect, request, render_template_string, Response
from datetime import datetime
import pandas as pd
from prophet import Prophet
import plotly.graph_objs as go
from plotly.offline import plot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)

# QuickBooks API environment variables
CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

# ---------- OAuth Token ----------
def get_access_token():
    url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    auth = (CLIENT_ID, CLIENT_SECRET)
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}

    response = requests.post(url, headers=headers, data=data, auth=auth)
    print("DEBUG Raw QuickBooks P&L Response:", response.text)
    if response.status_code != 200:
        print("QuickBooks token error:", response.text)
        return None
    return response.json().get("access_token")

# ---------- Fetch P&L Data ----------
def fetch_pnl_report():
    token = get_access_token()
    if not token:
        return []

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        # Fallback mock data for testing
        return [
            {"Month": "Jan 2025", "Revenue": 90000, "Expenses": 30000, "NetIncome": 60000},
            {"Month": "Feb 2025", "Revenue": 105000, "Expenses": 35000, "NetIncome": 70000},
            {"Month": "Mar 2025", "Revenue": 98000, "Expenses": 32000, "NetIncome": 66000},
            {"Month": "Apr 2025", "Revenue": 110000, "Expenses": 36000, "NetIncome": 74000},
            {"Month": "May 2025", "Revenue": 120000, "Expenses": 38000, "NetIncome": 82000},
            {"Month": "Jun 2025", "Revenue": 115000, "Expenses": 34000, "NetIncome": 81000},
        ]
    return []

# ---------- Forecast Logic ----------
def forecast_all_metrics(df):
    results = {}
    for metric in ["NetIncome", "Revenue", "Expenses"]:
        df_prophet = pd.DataFrame()
        df_prophet["ds"] = pd.to_datetime(df["Month"])
        df_prophet["y"] = df[metric]

        model = Prophet(yearly_seasonality=True, daily_seasonality=False)
        model.fit(df_prophet)

        future = model.make_future_dataframe(periods=3, freq="M")
        forecast = model.predict(future)
        results[metric] = forecast[["ds", "yhat"]]
    return results

# ---------- Chart Builder ----------
def build_forecast_chart(df, forecasts):
    traces = []
    traces.append(go.Scatter(x=df["Month"], y=df["Revenue"], mode="lines+markers", name="Actual Revenue"))
    traces.append(go.Scatter(x=df["Month"], y=df["Expenses"], mode="lines+markers", name="Actual Expenses"))
    traces.append(go.Scatter(x=df["Month"], y=df["NetIncome"], mode="lines+markers", name="Actual Net Income"))

    for metric, forecast_df in forecasts.items():
        traces.append(go.Scatter(
            x=forecast_df["ds"], y=forecast_df["yhat"], mode="lines+markers", 
            name=f"Forecasted {metric}"
        ))

    layout = go.Layout(
        title="P&L Forecast (Revenue, Expenses, Net Income)",
        xaxis=dict(title="Month"),
        yaxis=dict(title="USD"),
        template="plotly_white"
    )

    fig = go.Figure(data=traces, layout=layout)
    return plot(fig, output_type="div", include_plotlyjs=True)

# ---------- Forecast Table ----------
def build_forecast_table(forecasts):
    return pd.DataFrame({
        "Month": forecasts["NetIncome"]["ds"].tail(3).dt.strftime("%b %Y"),
        "Forecasted Revenue": forecasts["Revenue"]["yhat"].tail(3).round(2),
        "Forecasted Expenses": forecasts["Expenses"]["yhat"].tail(3).round(2),
        "Forecasted Net Income": forecasts["NetIncome"]["yhat"].tail(3).round(2)
    })

# ---------- Routes ----------
@app.route("/")
def index():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    auth_url = (
        "https://appcenter.intuit.com/connect/oauth2?"
        f"client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        "&response_type=code&scope=com.intuit.quickbooks.accounting&state=secureRandomState"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl_route():
    return json.dumps(fetch_pnl_report())

@app.route("/forecast")
def forecast_route():
    data = fetch_pnl_report()
    if not data:
        return "No P&L data available."

    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])
    forecasts = forecast_all_metrics(df)

    avg_net_income = forecasts["NetIncome"]["yhat"].tail(3).mean()
    chart_html = build_forecast_chart(df, forecasts)
    table_html = build_forecast_table(forecasts).to_html(
        index=False, classes="forecast-table", border=0, justify="center"
    )

    # Styled Dashboard
    return render_template_string(f"""
        <html>
        <head>
            <title>Clariqor Financial Dashboard</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: auto;
                    padding: 20px;
                    color: #333;
                    background-color: #fafafa;
                }}
                h1 {{
                    color: #1a1a1a;
                    text-align: center;
                    margin-bottom: 10px;
                }}
                h2 {{
                    margin-top: 30px;
                    text-align: center;
                }}
                p {{
                    font-size: 18px;
                    text-align: center;
                }}
                .forecast-table {{
                    margin: 20px auto;
                    border-collapse: collapse;
                    font-size: 16px;
                    min-width: 500px;
                }}
                .forecast-table th, .forecast-table td {{
                    padding: 10px;
                    text-align: center;
                    border: 1px solid #ccc;
                }}
                .forecast-table tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
                .export-link {{
                    display: block;
                    text-align: center;
                    margin-top: 20px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <h1>Financial Forecast Dashboard</h1>
            <p><strong>Average Net Income (Next 3 Months):</strong> ${avg_net_income:,.2f}</p>
            {chart_html}
            <h2>Forecast Details</h2>
            {table_html}
            <a href="/export" class="export-link">Download Forecast as CSV</a>
        </body>
        </html>
    """)

@app.route("/export")
def export_forecast():
    data = fetch_pnl_report()
    if not data:
        return Response("No P&L data available", status=400)

    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])
    forecasts = forecast_all_metrics(df)
    forecast_df = build_forecast_table(forecasts)

    csv_data = forecast_df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=forecast.csv"}
    )

# Run app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
