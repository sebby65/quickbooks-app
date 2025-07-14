import os
import io
import traceback
import pandas as pd
from flask import Flask, redirect, request, session, url_for, render_template, send_file
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from flask_session import Session
from transform_pnl_data import transform_qb_to_df, generate_forecast
from fetch_qb_data import fetch_profit_and_loss
from email_utils import send_email_report

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# QuickBooks config
CLIENT_ID = os.environ.get("QB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")
BASE_URL = "https://sandbox-quickbooks.api.intuit.com" if ENVIRONMENT == "sandbox" else "https://quickbooks.api.intuit.com"

@app.route("/")
def index():
    return render_template("index.html", 
        error=session.pop("forecast_error", None),
        forecast=session.pop("forecast", None),
        revenue=session.pop("revenue", None),
        cost=session.pop("cost", None),
        invoice_count=session.pop("invoice_count", None)
    )

@app.route("/connect")
def connect():
    auth_client = AuthClient(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    environment=ENVIRONMENT,
    redirect_uri=REDIRECT_URI
)
    try:
        auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
        session['auth_client'] = auth_client.__dict__
        return redirect(auth_url)
    except AuthClientError as e:
        return f"Error generating auth URL: {e}"

@app.route("/callback")
def callback():
    auth_client_data = session.get('auth_client')
    if not auth_client_data:
        return redirect(url_for('index'))
    try:
        auth_client.get_bearer_token(request.args.get('code'))
        session['access_token'] = auth_client.access_token
        session['realm_id'] = request.args.get('realmId')
        return redirect(url_for('index'))
    except AuthClientError as e:
        return f"Error getting bearer token: {e}"

@app.route("/forecast", methods=['POST'])
def forecast():
    access_token = session.get('access_token')
    realm_id = session.get('realm_id')
    months = int(request.args.get("range", 12))

    if not access_token or not realm_id:
        session["forecast_error"] = "Missing access token or realm ID."
        return redirect(url_for('index'))

    try:
        raw_data = fetch_profit_and_loss(access_token, realm_id)
        df = transform_qb_to_df(raw_data)
        df = df.sort_values("date").tail(months)

        forecast_df = generate_forecast(df)
        session["forecast"] = round(forecast_df['forecast'].iloc[-1], 2)
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
    data = session.get("csv_data")
    if not data:
        return "No data available", 400
    return send_file(io.BytesIO(data.encode()), mimetype="text/csv", as_attachment=True, download_name="forecast.csv")

@app.route("/email", methods=["POST"])
def email():
    email = request.form.get("email")
    csv_data = session.get("csv_data")
    if not csv_data:
        return "No data available", 400
    try:
        send_email_report(email, csv_data)
        return "Email sent"
    except Exception as e:
        app.logger.error(traceback.format_exc())
        return f"Email failed: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
