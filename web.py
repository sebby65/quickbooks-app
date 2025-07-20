from flask import Flask, jsonify, render_template_string
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from datetime import datetime

app = Flask(__name__)

# Mock P&L data (replace with actual QuickBooks API pull later)
def fetch_pnl_report():
    data = [
        {"Month": "2025-01-01", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
        {"Month": "2025-02-01", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
        {"Month": "2025-03-01", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
        {"Month": "2025-04-01", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
        {"Month": "2025-05-01", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
        {"Month": "2025-06-01", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
        {"Month": "2025-07-01", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
    ]
    return pd.DataFrame(data)

# Build forecast and visualizations
def build_forecast(df):
    df["Month"] = pd.to_datetime(df["Month"])
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]

    # Prophet model
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="ME")  # Month-end to avoid warnings
    forecast = model.predict(future)

    # Merge forecasts into main df
    df_full = pd.merge(df, forecast[["ds", "yhat"]], left_on="Month", right_on="ds", how="outer")
    df_full.drop(columns=["ds"], inplace=True)
    df_full.rename(columns={"yhat": "Forecast"}, inplace=True)

    # Add a simple smoothed trend (rolling mean)
    df_full["Smoothed"] = df_full["NetIncome"].rolling(window=3, min_periods=1).mean()

    # Remove rows that are fully empty (no actual or forecast)
    df_full = df_full.dropna(subset=["Forecast"], how="all")

    # Build plot
    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["NetIncome"], "bo-", label="Actual Net Income")
    plt.plot(forecast["ds"], forecast["yhat"], "kx--", label="Forecast")
    plt.plot(df_full["Month"], df_full["Smoothed"], "g:", label="Smoothed Trend")

    # Peak annotation
    peak = df["NetIncome"].max()
    if peak > 0:
        peak_date = df.loc[df["NetIncome"].idxmax(), "Month"]
        plt.annotate(f"Peak: ${peak:,.0f}", xy=(peak_date, peak), xytext=(peak_date, peak + 50000),
                     arrowprops=dict(facecolor='black', shrink=0.05))

    plt.title("Financial Forecast Summary", fontsize=16, fontweight="bold")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)

    # Convert to image
    img = BytesIO()
    plt.tight_layout()
    plt.savefig(img, format="png")
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()

    # Compute average forecasted net income
    avg_forecast = forecast["yhat"].tail(3).mean()
    negative_trend = avg_forecast < 0

    # Render HTML
    warning_text = f"⚠️ Projected negative trend with average Net Income of ${avg_forecast:,.2f}." if negative_trend else ""
    warning_color = "red" if negative_trend else "black"

    table_html = df_full.to_html(classes="table", index=False, float_format=lambda x: f"${x:,.0f}")

    html = f"""
    <h1>Financial Forecast Summary</h1>
    <h3 style="color:{warning_color};">{warning_text}</h3>
    <img src="data:image/png;base64,{plot_url}" style="max-width:100%;"/>
    <h2>Monthly Profit & Loss</h2>
    {table_html}
    """

    return html

# Routes
@app.route("/")
def home():
    return "Clariqor Financial Forecast App is running!"

@app.route("/connect")
def connect():
    return "QuickBooks OAuth connection would go here. (Placeholder route so it doesn’t 404.)"

@app.route("/pnl")
def pnl():
    df = fetch_pnl_report()
    return jsonify({"data": df.to_dict(orient="records")})

@app.route("/forecast")
def forecast():
    df = fetch_pnl_report()
    html = build_forecast(df)
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
