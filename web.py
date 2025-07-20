import os
from flask import Flask, jsonify, render_template_string
from datetime import datetime
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import io
import base64

app = Flask(__name__)

# --- Sample P&L Data (replace with QuickBooks integration later) ---
P_AND_L = [
    {"Month": "2025-01-01", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
    {"Month": "2025-02-01", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
    {"Month": "2025-03-01", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
    {"Month": "2025-04-01", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
    {"Month": "2025-05-01", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
    {"Month": "2025-06-01", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
    {"Month": "2025-07-01", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
]

# --- Helper: Prepare DataFrame ---
def get_df():
    df = pd.DataFrame(P_AND_L)
    df["Month"] = pd.to_datetime(df["Month"])
    return df

# --- Forecast using Prophet ---
def forecast_net_income(df):
    df_prophet = df[["Month", "NetIncome"]].rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(df_prophet)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)

    df_merged = pd.merge(df, forecast[["ds", "yhat"]], how="right", left_on="Month", right_on="ds")
    df_merged.rename(columns={"yhat": "Forecast"}, inplace=True)
    df_merged.drop(columns=["ds"], inplace=True)
    return df_merged, forecast

# --- Generate Forecast Chart ---
def generate_chart(df):
    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["NetIncome"], label="Actual Net Income", color="blue", marker="o")
    plt.plot(df["Month"], df["Forecast"], label="Forecast", linestyle="--", color="orange", marker="x")

    # Add smoothed trend
    df["Smoothed"] = df["NetIncome"].rolling(window=2, min_periods=1).mean()
    plt.plot(df["Month"], df["Smoothed"], label="Smoothed Trend", linestyle=":", color="green")

    # Highlight peak
    peak_idx = df["NetIncome"].idxmax()
    peak_val = df["NetIncome"].max()
    if not pd.isna(peak_val) and peak_val > 0:
        plt.annotate(f"Peak: ${peak_val:,.0f}",
                     (df.loc[peak_idx, "Month"], peak_val),
                     textcoords="offset points", xytext=(0, 10), ha="center")

    # Format y-axis as currency
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))

    plt.title("Financial Forecast Summary", fontsize=16, fontweight="bold")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(alpha=0.3)

    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format="png")
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode()

# --- Routes ---
@app.route("/pnl")
def pnl():
    return jsonify({"data": P_AND_L})

@app.route("/forecast")
def forecast():
    df = get_df()
    df_forecast, _ = forecast_net_income(df)
    chart = generate_chart(df_forecast)

    avg_next_3 = df_forecast.tail(3)["Forecast"].mean()
    warning = ""
    if avg_next_3 < 0:
        warning = f"⚠️ Projected negative trend with average Net Income of ${avg_next_3:,.2f}."

    table_html = df_forecast.to_html(index=False, float_format=lambda x: f"${x:,.0f}" if pd.notna(x) else "-")

    html = f"""
    <h2>Financial Forecast Summary</h2>
    <p style='color: {"red" if warning else "green"}; font-weight:bold;'>{warning}</p>
    <img src="data:image/png;base64,{chart}" />
    <h3>Monthly Profit & Loss</h3>
    {table_html}
    """
    return render_template_string(html)

@app.route("/")
def dashboard():
    df = get_df()
    df_forecast, _ = forecast_net_income(df)
    chart = generate_chart(df_forecast)
    avg_next_3 = df_forecast.tail(3)["Forecast"].mean()

    # Build a simple homepage combining everything
    html = f"""
    <html>
    <head><title>Financial Dashboard</title></head>
    <body style='font-family: Arial; margin: 20px;'>
        <h1>Financial Dashboard</h1>
        <p><b>Average Net Income (Next 3 Months):</b> ${avg_next_3:,.2f}</p>
        <img src="data:image/png;base64,{chart}" />
        <p><a href='/pnl'>View Raw JSON (P&L)</a> | <a href='/forecast'>Detailed Forecast Page</a></p>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
