import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, jsonify, render_template_string
from prophet import Prophet
from datetime import datetime, timedelta
from io import BytesIO
import base64

app = Flask(__name__)

# ---------------- Mock / Placeholder Data ----------------
# (In production, fetch this from QuickBooks API dynamically)
PERSISTENT_PNL = [
    {"Month": "Jan 2025", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
    {"Month": "Feb 2025", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
    {"Month": "Mar 2025", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
    {"Month": "Apr 2025", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
    {"Month": "May 2025", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
    {"Month": "Jun 2025", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
    {"Month": "Jul 2025", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
]

# ---------------- Utility Functions ----------------

def build_forecast(data):
    """Creates a 3-month Prophet forecast for Net Income."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])
    df = df.sort_values("Month")

    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)

    # Extract forecast data for the new months
    future_forecast = forecast[["ds", "yhat"]].tail(3)
    avg_net_income = future_forecast["yhat"].mean()

    return future_forecast.to_dict(orient="records"), avg_net_income


def generate_chart(data, forecast):
    """Generates a Matplotlib chart combining actual Net Income and forecast."""
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])
    df = df.sort_values("Month")

    forecast_df = pd.DataFrame(forecast)
    forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])

    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["NetIncome"], label="Actual Net Income", marker="o")
    plt.plot(forecast_df["ds"], forecast_df["yhat"], label="Forecast", linestyle="--", marker="x")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.title("Net Income Forecast")
    plt.legend()
    plt.grid(True)

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close()
    return img_base64


# ---------------- Flask Routes ----------------

@app.route("/")
def dashboard():
    forecast_data, avg_net_income = build_forecast(PERSISTENT_PNL)
    chart_img = generate_chart(PERSISTENT_PNL, forecast_data)

    # Build table rows for display
    pnl_rows = "".join(
        f"<tr><td>{row['Month']}</td><td>${row['Revenue']:,}</td>"
        f"<td>${row['Expenses']:,}</td><td>${row['NetIncome']:,}</td></tr>"
        for row in PERSISTENT_PNL
    )

    # Render HTML directly (keeps it simple — no external templates)
    html = f"""
    <html>
    <head>
        <title>Financial Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ font-size: 32px; }}
            h2 {{ margin-top: 20px; }}
            table {{
                width: 100%; border-collapse: collapse; margin-top: 20px;
            }}
            table, th, td {{ border: 1px solid #ccc; }}
            th, td {{ padding: 8px; text-align: center; }}
            img {{ display: block; margin: 20px auto; max-width: 80%; }}
        </style>
    </head>
    <body>
        <h1>Financial Forecast Summary</h1>
        <h2>Average Net Income (Next 3 Months): ${avg_net_income:,.2f}</h2>
        <img src="data:image/png;base64,{chart_img}" alt="Net Income Forecast Chart">
        <h2>Monthly Profit & Loss</h2>
        <table>
            <tr><th>Month</th><th>Revenue</th><th>Expenses</th><th>Net Income</th></tr>
            {pnl_rows}
        </table>
    </body>
    </html>
    """
    return html


@app.route("/pnl")
def pnl_api():
    """Returns raw Profit & Loss data as JSON."""
    return jsonify({"data": PERSISTENT_PNL})


@app.route("/forecast")
def forecast_api():
    """Returns 3-month forecast data and average net income as JSON."""
    forecast_data, avg_net_income = build_forecast(PERSISTENT_PNL)
    return jsonify({"forecast": forecast_data, "average_net_income": avg_net_income})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
