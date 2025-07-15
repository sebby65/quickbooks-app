import os
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from prophet import Prophet
import pandas as pd
from io import BytesIO

from fetch_qb_data import fetch_qb_data
from transform_pnl_data import transform_qb_to_df
from email_utils import send_forecast_email

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "production")
REALM_ID = os.getenv("QB_REALM")

try:
    auth_client = AuthClient(CLIENT_ID, CLIENT_SECRET, ENVIRONMENT, REDIRECT_URI)
except Exception as e:
    print("Error initializing AuthClient:", e)
    raise

@app.route("/")
def home():
    return render_template("financial_dashboard (2).html")

@app.route("/connect")
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return jsonify({'auth_url': auth_url})

@app.route("/callback")
def callback():
    code = request.args.get('code')
    auth_client.get_bearer_token(code)
    return jsonify({'status': 'connected'})

@app.route("/forecast", methods=["POST"])
def forecast():
    try:
        client = QuickBooks(
            auth_client=auth_client,
            refresh_token=auth_client.refresh_token,
            company_id=REALM_ID,
        )
        pnl_data = fetch_qb_data(client)
        df = transform_qb_to_df(pnl_data)

        model = Prophet()
        model.fit(df.rename(columns={"ds": "ds", "y": "y"}))
        future = model.make_future_dataframe(periods=12, freq="M")
        forecast = model.predict(future)

        forecast_data = forecast[["ds", "yhat"]].rename(columns={"ds": "date", "yhat": "forecast"})
        forecast_data["date"] = forecast_data["date"].dt.strftime('%Y-%m')

        app.config["forecast_df"] = forecast_data
        return jsonify(forecast_data.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/download")
def download():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast available to download.", 400
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="forecast.csv")

@app.route("/email", methods=["POST"])
def email():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast available to email.", 400
    to_email = request.form.get("email", os.getenv("EMAIL_RECEIVER"))
    try:
        send_forecast_email(to_email, df)
        return render_template("form (2).html", email_status="Email sent successfully.")
    except Exception as e:
        return render_template("form (2).html", email_status=f"Failed to send email: {e}")

if __name__ == "__main__":
    app.run(debug=True)
