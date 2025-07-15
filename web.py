import os
from flask import Flask, render_template, redirect, request, session, send_file
from dotenv import load_dotenv
from fetch_qb_data import fetch_qb_data
from transform_pnl_data import transform_data
from email_utils import send_email_with_attachment
from auth import AuthClient
import pandas as pd
from prophet import Prophet
from io import StringIO
from datetime import datetime

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "devkey")

auth_client = AuthClient()

@app.route("/")
def index():
    forecast_data = session.pop("forecast_data", None)
    email_status = session.pop("email_status", None)
    return render_template("index.html", chart_data=forecast_data, email_status=email_status)

@app.route("/connect")
def connect():
    return redirect(auth_client.get_auth_url())

@app.route("/callback")
def callback():
    auth_client.get_bearer_token(request.args.get('code'))
    session["realm_id"] = request.args.get("realmId")
    return redirect("/")

@app.route("/forecast", methods=["POST"])
def forecast():
    months = int(request.args.get("range", 12))
    realm_id = session.get("realm_id")
    if not realm_id:
        return redirect("/connect")

    raw_data = fetch_qb_data(auth_client, realm_id)
    df = transform_data(raw_data)

    df = df.sort_values("ds").tail(months)  # ✅ FIXED COLUMN NAME
    model = Prophet()
    model.fit(df.rename(columns={"ds": "ds", "y": "y"}))
    future = model.make_future_dataframe(periods=3, freq="M")
    forecast = model.predict(future)

    merged = pd.merge(df, forecast[["ds", "yhat"]], on="ds", how="left")
    merged = merged.rename(columns={"yhat": "forecast"})
    forecast_dict = merged[["ds", "y", "forecast"]].to_dict(orient="records")

    session["forecast_data"] = forecast_dict
    session["csv_data"] = merged[["ds", "forecast"]].to_csv(index=False)
    return redirect("/")

@app.route("/download")
def download_csv():
    csv = session.get("csv_data")
    if not csv:
        return "No data available", 400

    buf = StringIO(csv)
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name="forecast.csv"
    )

@app.route("/email", methods=["POST"])
def email():
    recipient = request.form.get("email")
    csv = session.get("csv_data")

    if not recipient or not csv:
        return "Missing email or data", 400

    buf = StringIO(csv)
    send_email_with_attachment(
        recipient_email=recipient,
        subject="Your Clariqor Forecast Report",
        body="Attached is your latest financial forecast from Clariqor.",
        attachment_bytes=buf.getvalue().encode(),
        filename="forecast.csv"
    )

    session["email_status"] = "📧 Forecast sent successfully!"
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
