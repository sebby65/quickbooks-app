from flask import Flask, jsonify, Response
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

app = Flask(__name__)

# Mock P&L data (replace this with your QuickBooks API data fetch)
def fetch_pnl_report():
    return [
        {"Month": "2025-01-01", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
        {"Month": "2025-02-01", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
        {"Month": "2025-03-01", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
        {"Month": "2025-04-01", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
        {"Month": "2025-05-01", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
        {"Month": "2025-06-01", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
        {"Month": "2025-07-01", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
    ]

# Build Prophet forecast
def build_forecast(df):
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet(yearly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)
    forecast = forecast[["ds", "yhat"]].rename(columns={"ds": "Month", "yhat": "Forecast"})
    return forecast

# Generate the combined dashboard (graph + table + summary)
@app.route("/")
def dashboard():
    # Get data
    data = fetch_pnl_report()
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"])

    # Forecast
    forecast = build_forecast(df)
    merged = pd.merge(df, forecast, on="Month", how="outer")

    # Calculate metrics
    avg_forecast = forecast["Forecast"].tail(3).mean()
    peak_income = df["NetIncome"].max()

    # Generate chart
    plt.figure(figsize=(10, 6))
    plt.plot(df["Month"], df["NetIncome"], label="Actual Net Income", marker="o", color="blue")
    plt.plot(forecast["Month"], forecast["Forecast"], label="Forecast", linestyle="--", marker="x", color="orange")
    
    # Smoothed trend line
    smoothed = np.convolve(df["NetIncome"], np.ones(3)/3, mode="valid")
    smoothed_x = df["Month"].iloc[1:-1]
    plt.plot(smoothed_x, smoothed, label="Smoothed Trend", linestyle=":", color="green")

    # Annotate peak
    peak_month = df.loc[df["NetIncome"].idxmax(), "Month"]
    plt.annotate(f"Peak: ${peak_income:,.0f}", xy=(peak_month, peak_income),
                 xytext=(peak_month, peak_income + 50000),
                 arrowprops=dict(facecolor="black", arrowstyle="->"))

    plt.title("Financial Forecast Summary", fontsize=16, fontweight="bold")
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True)

    img = io.BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    # Build HTML dashboard
    html = f"""
    <h2>Financial Forecast Summary</h2>
    <h3 style="color: {'red' if avg_forecast < 0 else 'green'};">
        {'⚠️ Warning: Projected negative trend' if avg_forecast < 0 else 'Projected positive trend'}
        with average Net Income of ${avg_forecast:,.2f}.
    </h3>
    <img src="data:image/png;base64,{plot_url}" style="max-width: 100%; height: auto;">

    <h3>Monthly Profit & Loss</h3>
    {merged.to_html(index=False)}
    """
    return Response(html, mimetype="text/html")

# Keep /pnl and /forecast routes (for direct API access)
@app.route("/pnl")
def pnl():
    return jsonify({"data": fetch_pnl_report()})

@app.route("/forecast")
def forecast_view():
    df = pd.DataFrame(fetch_pnl_report())
    df["Month"] = pd.to_datetime(df["Month"])
    forecast = build_forecast(df)
    return jsonify(forecast.to_dict(orient="records"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
