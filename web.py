from flask import Flask, jsonify, render_template_string
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64

app = Flask(__name__)

# --- Mock P&L data (replace with QuickBooks API in production) ---
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

# --- Prophet Forecasting Function ---
def make_forecast(df):
    prophet_df = df[["Month", "NetIncome"]].rename(columns={"Month": "ds", "NetIncome": "y"})
    m = Prophet(daily_seasonality=False, yearly_seasonality=False)
    m.fit(prophet_df)

    future = m.make_future_dataframe(periods=3, freq="ME")  # Avoid 'M' deprecation
    forecast = m.predict(future)
    forecast = forecast[["ds", "yhat"]]

    merged = pd.merge(df, forecast, left_on="Month", right_on="ds", how="outer")
    merged = merged.drop(columns=["ds"]).rename(columns={"yhat": "Forecast"})

    # Fill future NaN revenue/expenses with 0 for cleaner table display
    merged["Revenue"] = merged["Revenue"].fillna(0)
    merged["Expenses"] = merged["Expenses"].fillna(0)

    # Simple smoothed trend (rolling average on NetIncome)
    merged["Smoothed"] = merged["NetIncome"].rolling(window=3, min_periods=1).mean().fillna(0)

    return merged, forecast

# --- Generate Chart ---
def generate_chart(df, avg_net_income):
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(df["Month"], df["NetIncome"], "bo-", label="Actual Net Income")
    ax.plot(df["Month"], df["Forecast"], "x--", color="orange", label="Forecast")
    ax.plot(df["Month"], df["Smoothed"], "g:", label="Smoothed Trend")

    # Annotate peak
    peak_row = df.loc[df["NetIncome"].idxmax()]
    ax.annotate(f"Peak: ${peak_row['NetIncome']:,}", xy=(peak_row["Month"], peak_row["NetIncome"]),
                xytext=(0, 30), textcoords="offset points", ha="center", fontsize=9,
                arrowprops=dict(arrowstyle="->", color="black"))

    # Axis & labels
    ax.set_title("Financial Forecast Summary", fontsize=16, weight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net Income ($)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.legend()
    plt.xticks(rotation=30)

    # Convert to base64
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return chart_base64

# --- Flask Routes ---
@app.route("/")
def home():
    return "<h2>Welcome to Clariqor Financial Forecast</h2><p>Visit /pnl or /forecast to view reports.</p>"

@app.route("/pnl")
def pnl():
    df = fetch_pnl_report()
    return jsonify({"data": df.to_dict(orient="records")})

@app.route("/forecast")
def forecast():
    df = fetch_pnl_report()
    df["Month"] = pd.to_datetime(df["Month"])
    df, forecast_df = make_forecast(df)
    avg_net_income = forecast_df["yhat"][-3:].mean()

    chart_base64 = generate_chart(df, avg_net_income)

    # Build HTML output
    warning_html = ""
    if avg_net_income < 0:
        warning_html = f"<p style='color:red; font-weight:bold;'>⚠ Projected negative trend with average Net Income of ${avg_net_income:,.2f}.</p>"

    table_html = df.to_html(index=False, float_format=lambda x: f"${x:,.0f}")

    html = f"""
    <h1>Financial Forecast Summary</h1>
    {warning_html}
    <img src="data:image/png;base64,{chart_base64}" alt="Forecast Chart"/>
    <h2>Monthly Profit & Loss</h2>
    {table_html}
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
