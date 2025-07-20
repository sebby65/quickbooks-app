from flask import Flask, jsonify, render_template_string
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

app = Flask(__name__)

# Mock P&L data (replace later with live QuickBooks data)
pnl_data = [
    {"Month": "2025-01-01", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
    {"Month": "2025-02-01", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
    {"Month": "2025-03-01", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
    {"Month": "2025-04-01", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
    {"Month": "2025-05-01", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
    {"Month": "2025-06-01", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
    {"Month": "2025-07-01", "Revenue": 200, "Expenses": 0, "NetIncome": 200}
]

@app.route("/")
def home():
    return "QuickBooks Forecast App Running. Visit /pnl or /forecast."

@app.route("/connect")
def connect():
    return render_template_string("""
        <h2>QuickBooks OAuth Connection</h2>
        <p>Mock connection successful. (Live integration can be added later.)</p>
    """)

@app.route("/pnl")
def pnl():
    return jsonify({"data": pnl_data})

@app.route("/forecast")
def forecast():
    df = pd.DataFrame(pnl_data)

    # Ensure Month is datetime
    df["Month"] = pd.to_datetime(df["Month"], errors='coerce')
    df.sort_values("Month", inplace=True)

    # Forecast using Prophet
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet(yearly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)

    # Forecast 3 future months
    future = model.make_future_dataframe(periods=3, freq="MS")
    forecast = model.predict(future)

    # Merge forecast into display dataframe
    forecast_data = forecast[["ds", "yhat"]].rename(columns={"ds": "Month", "yhat": "Forecast"})
    display_df = pd.merge(df, forecast_data, on="Month", how="outer")

    # Add a smoothed trendline (rolling average)
    display_df["Smoothed"] = display_df["NetIncome"].rolling(window=3, min_periods=1).mean()

    # Format Month safely for display
    if not pd.api.types.is_datetime64_any_dtype(display_df["Month"]):
        display_df["Month"] = pd.to_datetime(display_df["Month"], errors='coerce')
    display_df["Month"] = display_df["Month"].dt.strftime("%b %Y")

    # Build the plot
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(display_df["Month"], display_df["NetIncome"], label="Actual Net Income", marker="o", color="blue")
    ax.plot(display_df["Month"], display_df["Forecast"], label="Forecast", linestyle="--", marker="x", color="black")
    ax.plot(display_df["Month"], display_df["Smoothed"], label="Smoothed Trend", linestyle=":", color="green")

    # Highlight peak Net Income
    if not df.empty:
        peak_idx = df["NetIncome"].idxmax()
        if pd.notnull(peak_idx):
            peak_month = df.loc[peak_idx, "Month"].strftime("%b %Y")
            peak_value = df.loc[peak_idx, "NetIncome"]
            ax.annotate(f"Peak: ${peak_value:,.0f}",
                        xy=(peak_idx, peak_value), xycoords=("data", "data"),
                        xytext=(0, 40), textcoords="offset points",
                        ha="center", arrowprops=dict(arrowstyle="->", color="black"))

    ax.set_title("Financial Forecast Summary", fontsize=14, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net Income ($)")
    ax.legend()
    ax.grid(True)

    # Save chart as base64
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    # Warning if negative trend
    avg_forecast = display_df["Forecast"].tail(3).mean()
    warning = ""
    if avg_forecast < 0:
        warning = f"⚠️ Projected negative trend with average Net Income of ${avg_forecast:,.2f}."

    # Render HTML
    html = f"""
    <h2>Financial Forecast Summary</h2>
    <p style="color: red;">{warning}</p>
    <img src="data:image/png;base64,{chart_base64}" alt="Forecast Chart" style="max-width: 100%;"><br>
    <h3>Monthly Profit & Loss</h3>
    {display_df.to_html(index=False, justify="center")}
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
