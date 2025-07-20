from flask import Flask, jsonify, Response
import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet
import io, base64
from datetime import datetime

app = Flask(__name__)

# --- Mock data (replace with real QuickBooks API later) ---
DATA = [
    {"Month": "Jan 2025", "Revenue": 0, "Expenses": 0, "NetIncome": 0},
    {"Month": "Feb 2025", "Revenue": 40000, "Expenses": 0, "NetIncome": 40000},
    {"Month": "Mar 2025", "Revenue": 500000, "Expenses": 100000, "NetIncome": 400000},
    {"Month": "Apr 2025", "Revenue": 1002, "Expenses": 0, "NetIncome": 1002},
    {"Month": "May 2025", "Revenue": 800, "Expenses": 10000, "NetIncome": -9200},
    {"Month": "Jun 2025", "Revenue": 1000, "Expenses": 20000, "NetIncome": -19000},
    {"Month": "Jul 2025", "Revenue": 200, "Expenses": 0, "NetIncome": 200},
]

# --- Helper: Convert list to DataFrame ---
def to_df(data):
    df = pd.DataFrame(data)
    df["Month"] = pd.to_datetime(df["Month"], format="%b %Y")  # Fix format warning
    df = df.sort_values("Month")
    return df

# --- Forecast builder with Prophet ---
def build_forecast(df):
    prophet_df = df.rename(columns={"Month": "ds", "NetIncome": "y"})[["ds", "y"]]
    model = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=3, freq="ME")  # fix 'M' deprecation
    forecast = model.predict(future)

    # Extract forecast portion (last 3 months)
    forecast = forecast[["ds", "yhat"]].tail(3)
    forecast.rename(columns={"ds": "Month", "yhat": "Forecast"}, inplace=True)
    return forecast

# --- Generate insights based on forecast trend ---
def generate_insights(df, forecast):
    avg_next_3 = forecast["Forecast"].mean()
    if avg_next_3 < 0:
        note = f"⚠️ Warning: Projected negative trend with average Net Income of ${avg_next_3:,.2f}."
    elif df["NetIncome"].max() > avg_next_3 * 5:
        note = "Note: Forecast skewed by large income spikes; trend may not reflect typical performance."
    else:
        note = f"Average Net Income (Next 3 Months): ${avg_next_3:,.2f}"
    return note, avg_next_3

# --- Route: Profit & Loss raw data ---
@app.route("/pnl", methods=["GET"])
def pnl():
    df = to_df(DATA)
    return jsonify({"data": df.to_dict(orient="records")})

# --- Route: Forecast chart and insights ---
@app.route("/forecast", methods=["GET"])
def forecast():
    df = to_df(DATA)
    forecast = build_forecast(df)

    # Merge for combined table/chart data
    combined = pd.merge(df, forecast, on="Month", how="outer").sort_values("Month")
    combined["Forecast"] = combined["Forecast"].fillna(0)

    # Insights & average
    note, avg_next_3 = generate_insights(df, forecast)

    # Chart setup
    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["NetIncome"], marker="o", label="Actual Net Income", color="blue")
    plt.plot(forecast["Month"], forecast["Forecast"], marker="x", linestyle="--", color="orange", label="Forecast")

    # Moving average for smoother visual
    df["Smoothed"] = df["NetIncome"].rolling(window=2, min_periods=1).mean()
    plt.plot(df["Month"], df["Smoothed"], color="green", linestyle=":", label="Smoothed Trend")

    # Annotate peak point
    max_point = df.loc[df["NetIncome"].idxmax()]
    plt.annotate(f"Peak: ${max_point['NetIncome']:,.0f}",
                 (max_point["Month"], max_point["NetIncome"]),
                 xytext=(10, 30), textcoords="offset points", arrowprops=dict(arrowstyle="->"))

    plt.title("Financial Forecast Summary", fontsize=16, weight="bold")
    plt.suptitle(f"Average Net Income (Next 3 Months): ${avg_next_3:,.2f}", fontsize=12, weight="bold", x=0.15, y=0.91)
    plt.xlabel("Month")
    plt.ylabel("Net Income ($)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    # Save plot as base64 image for inline response
    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    img_base64 = base64.b64encode(img.read()).decode("utf-8")
    plt.close()

    # Build HTML page
    html = f"""
    <html>
    <body>
        <h2>Financial Forecast Summary</h2>
        <p><b>{note}</b></p>
        <img src="data:image/png;base64,{img_base64}" width="800"/>
        <h3>Monthly Profit & Loss</h3>
        {combined.to_html(index=False, justify="center")}
    </body>
    </html>
    """
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
