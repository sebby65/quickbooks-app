from flask import Flask, jsonify, render_template_string
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64

app = Flask(__name__)

# Mock data for P&L
data = [
    {"Month": "2025-01-01", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
    {"Month": "2025-02-01", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
    {"Month": "2025-03-01", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
    {"Month": "2025-04-01", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
    {"Month": "2025-05-01", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
    {"Month": "2025-06-01", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
    {"Month": "2025-07-01", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
]
df = pd.DataFrame(data)
df["Month"] = pd.to_datetime(df["Month"])

@app.route("/")
def home():
    return "Clariqor Financial Dashboard Running"

@app.route("/connect")
def connect():
    return "<h2>QuickBooks OAuth Connection</h2><p>Mock connection successful. (Live integration can be added later.)</p>"

@app.route("/pnl")
def pnl():
    df_copy = df.copy()
    df_copy["Month"] = df_copy["Month"].dt.strftime("%b %Y")
    return jsonify({"data": df_copy.to_dict(orient="records")})

@app.route("/forecast")
def forecast():
    df_prophet = df[["Month", "NetIncome"]].rename(columns={"Month": "ds", "NetIncome": "y"})
    model = Prophet()
    model.fit(df_prophet)

    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)

    # Merge for table output
    merged = pd.merge(future, forecast[["ds", "yhat"]], on="ds", how="left")
    merged = pd.merge(merged, df, left_on="ds", right_on="Month", how="left")
    merged.rename(columns={"ds": "Month", "yhat": "Forecast"}, inplace=True)

    # Rolling average as smoothed trend
    merged["Smoothed"] = merged["NetIncome"].rolling(window=3, min_periods=1).mean()

    # Format display values
    display_df = merged.copy()
    display_df["Month"] = display_df["Month"].dt.strftime("%b %Y")
    for col in ["Revenue", "Expenses", "NetIncome", "Forecast", "Smoothed"]:
        display_df[col] = display_df[col].apply(
            lambda x: f"${x:,.0f}" if pd.notnull(x) else "$0"
        )

    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(merged["Month"], merged["NetIncome"], label="Actual Net Income", color="blue", marker="o")
    ax.plot(merged["Month"], merged["Forecast"], label="Forecast", color="black", linestyle="--", marker="x")
    ax.plot(merged["Month"], merged["Smoothed"], label="Smoothed Trend", color="green", linestyle=":")

    # Highlight peak
    peak_idx = merged["NetIncome"].idxmax()
    peak_val = merged.loc[peak_idx, "NetIncome"]
    peak_date = merged.loc[peak_idx, "Month"]
    ax.annotate(f"Peak: ${peak_val:,.0f}", xy=(peak_date, peak_val),
                xytext=(peak_date, peak_val + peak_val * 0.1),
                arrowprops=dict(facecolor="black", arrowstyle="->"), ha="center")

    # Format axes
    ax.set_title("Financial Forecast Summary", fontsize=16, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net Income ($)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=30)
    ax.legend()

    # Add warning if negative forecast
    avg_next3 = forecast.tail(3)["yhat"].mean()
    warning = ""
    if avg_next3 < 0:
        warning = f"<p style='color:red; font-weight:bold;'>⚠ Projected negative trend with average Net Income of ${avg_next3:,.2f}.</p>"

    # Save plot
    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format="png")
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()

    # HTML page
    html = f"""
    <html>
    <body style="font-family: Arial; text-align: center;">
        {warning}
        <img src="data:image/png;base64,{plot_url}" style="max-width:90%;"><br>
        <h2>Monthly Profit & Loss</h2>
        {display_df.to_html(index=False, justify="center")}
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
