import os
from flask import Flask, render_template, request, redirect, send_file
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from dotenv import load_dotenv
from transform_pnl_data import transform_qb_to_df
from email_utils import send_forecast_email
from fetch_qb_data import fetch_qb_data
import pandas as pd
from prophet import Prophet
from io import BytesIO
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "sandbox")
REALM_ID = os.getenv("QB_REALM")

try:
    if ENVIRONMENT not in ['sandbox', 'production']:
        raise ValueError("Invalid QB_ENVIRONMENT: must be 'sandbox' or 'production'")
    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        environment=ENVIRONMENT,
        redirect_uri=REDIRECT_URI
    )
except Exception as e:
    print("Error initializing AuthClient:", e)
    raise SystemExit("AuthClient setup failed. Check QB_ENVIRONMENT and credentials.")

@app.route("/")
def home():
    return render_template("financial_dashboard.html")

@app.route("/connect")
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return redirect(auth_url)

@app.route("/callback")
def callback():
    auth_client.get_bearer_token(request.args.get("code"))
    return redirect("/")

@app.route("/forecast", methods=["POST"])
def get_pnl_report(realm_id, access_token):
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/reports/ProfitAndLoss"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    params = {
        "start_date": "2024-01-01",
        "end_date": "2024-06-30"
    }

    r = requests.get(url, headers=headers, params=params)
    report = r.json()

    if not report.get("Rows") or not report["Rows"].get("Row"):
        print("❌ No Profit & Loss data. Add more transactions.")
        return None

    print("✅ P&L data received!")
    return report

# Test it
pnl_report = get_pnl_report(realm_id, access_token)

@app.route("/download")
def download():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast to download", 400
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="forecast.csv")

@app.route("/email", methods=["POST"])
def email():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast to email", 400
    to_email = request.form.get("email", os.getenv("EMAIL_RECEIVER"))
    status = send_forecast_email(to_email, df)
    return render_template("financial_dashboard (2).html", email_status=status)

if __name__ == "__main__":
    app.run(debug=True)
