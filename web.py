from flask import Flask, render_template, request, jsonify
import logging
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

# Basic console logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    return render_template("financial_dashboard.html")

@app.route("/forecast", methods=["POST"])
def forecast():
    logger.info("→ POST /forecast received")
    try:
        qb_data = request.get_json()
        logger.info(f"payload: {qb_data}")
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        result = forecast_df.to_dict(orient="records")
        logger.info(f"forecast result: {result[:3]}... total {len(result)} rows")
        return jsonify(result)
    except Exception as e:
        logger.exception("Forecasting failed")
        return jsonify({"error": "Forecasting failed, check server logs"}), 500

if __name__ == "__main__":
    app.run(debug=True)
