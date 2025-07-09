from flask import Flask, render_template, jsonify
from transform_pnl_data import transform_qb_to_df, generate_forecast
import json

app = Flask(__name__)

@app.route("/dashboard")
def dashboard():
    return render_template("financial_dashboard.html")

@app.route("/forecast")
def forecast():
    try:
        # Replace this with real QB data fetching if needed
        with open("sample_qb_data.json") as f:
            qb_data = json.load(f)

        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        return jsonify(forecast_df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
