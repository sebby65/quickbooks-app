import os
import json
import csv
import io
import requests
import traceback
import pandas as pd
from flask import Flask, redirect, request, session, url_for, render_template, send_file
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from flask_session import Session
from datetime import datetime
from transform_pnl_data import transform_qb_to_df, generate_forecast
from fetch_qb_data import fetch_profit_and_loss
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")

# Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# QuickBooks
CLIENT_ID = os.environ.get("QB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")

if ENVIRONMENT == "sandbox":
    BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
else:
    BASE_URL = "https://quickbooks.api.intuit.com"

# Email
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", EMAIL_USER)

@app.route("/")
def index():
    error = session.pop("forecast_error", None)
    forecast = session.pop("forecast", None)
    revenue = session.pop("revenue", None)
    cost = session.pop("cost", None)
    invoice_count = session.pop("invoice_count", None)
    return render_template("index.html", error=error, forecast=forecast, revenue=revenue, cost=cost, invoice_count=invoice_count)

@app.route("/connect")
def connect():
    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        environment=ENVIRONMENT,
        redirect_uri=REDIRECT_URI,
    )
    try:
        auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
        session['auth_client'] = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'environment': ENVIRONMENT
        }
        return redirect(auth_url)
    except AuthClientError as e:
        return f"Error generating auth URL: {e}"

@app.route("/callback")
def callback():
    auth_client_data = session.get('auth_client')
    if not auth_client_data:
        return redirect(url_for('index'))

    auth_client = AuthClient(
        client_id=auth_client_data['client_id'],
        client_secret=auth_client_data['client_secret'],
        environment=auth_client_data['environment'],
        redirect_uri=auth_client_data['redirect_uri'],
    )

    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')

    try:
        auth_client.get_bearer_token(auth_code)
        session['access_token'] = auth_client.access_token
        session['realm_id'] = realm_id
        return redirect(url_for('index'))
    except AuthClientError as e:
        return f"Error getting bearer token: {e}"

@app.route("/forecast", methods=['POST'])
def forecast():
    access_token = session.get('access_token')
    realm_id = session.get('realm_id')
    range_months = int(request.args.get("range", 12))

    if not access_token or not realm_id:
        session["forecast_error"] = "Missing access token or realm ID."
        return redirect(url_for('index'))

    try:
        pnl_data = fetch_profit_and_loss(access_token, realm_id)
        df = transform_qb_to_df(pnl_data)

        if df.empty:
            raise ValueError("No usable data found in QuickBooks P&L report.")

        df = df.sort_values("date").tail(range_months)
        forecast_df = generate_forecast(df)
        forecast = forecast_df['forecast'].iloc[-1]

        session["forecast"] = round(forecast, 2)
        session["revenue"] = round(df['amount'].sum(), 2)
        session["cost"] = "N/A"
        session["invoice_count"] = len(df)

        session["csv_data"] = df.to_csv(index=False)

    except Exception as e:
        session["forecast_error"] = f"Forecast failed: {str(e)}"
        app.logger.error(traceback.format_exc())

    return redirect(url_for('index'))

@app.route("/download")
def download_csv():
    csv_data = session.get("csv_data", "")
    if not csv_data:
        return "No data to export", 400
    buffer = io.StringIO(csv_data)
    return send_file(io.BytesIO(buffer.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="forecast.csv")

@app.route("/email", methods=["POST"])
def email_report():
    csv_data = session.get("csv_data", "")
    email = request.form.get("email", EMAIL_RECEIVER)

    if not csv_data:
        return "No data to send", 400

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = email
        msg["Subject"] = "Your Clariqor Financial Forecast"

        msg.attach(MIMEText("Attached is your latest financial forecast from Clariqor.", "plain"))

        attachment = MIMEApplication(csv_data, Name="forecast.csv")
        attachment["Content-Disposition"] = 'attachment; filename="forecast.csv"'
        msg.attach(attachment)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)

        return "Email sent successfully"
    except Exception as e:
        app.logger.error(traceback.format_exc())
        return f"Email failed: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
