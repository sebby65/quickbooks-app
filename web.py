import os
import json
import requests
from flask import Flask, redirect, request, session, url_for, render_template
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from flask_session import Session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")

# Configure server-side session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# QuickBooks API credentials
CLIENT_ID = os.environ.get("QB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")  # 'sandbox' or 'production'

# Select base URL based on environment
if ENVIRONMENT == "sandbox":
    BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
else:
    BASE_URL = "https://quickbooks.api.intuit.com"

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
        session['refresh_token'] = auth_client.refresh_token
        session['realm_id'] = realm_id
        return redirect(url_for('index'))
    except AuthClientError as e:
        return f"Error getting bearer token: {e}"

def refresh_access_token():
    auth_client_data = session.get('auth_client')
    if not auth_client_data or 'refresh_token' not in session:
        return False

    auth_client = AuthClient(
        client_id=auth_client_data['client_id'],
        client_secret=auth_client_data['client_secret'],
        environment=auth_client_data['environment'],
        redirect_uri=auth_client_data['redirect_uri'],
    )

    try:
        auth_client.refresh(session['refresh_token'])
        session['access_token'] = auth_client.access_token
        session['refresh_token'] = auth_client.refresh_token
        return True
    except AuthClientError:
        return False

@app.route("/forecast", methods=['POST'])
def forecast():
    access_token = session.get('access_token')
    realm_id = session.get('realm_id')

    if not access_token or not realm_id:
        session["forecast_error"] = "Missing access token or realm ID."
        return redirect(url_for('index'))

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    def run_query(entity):
        query = f"SELECT * FROM {entity}"
        url = f"{BASE_URL}/v3/company/{realm_id}/query?query={query}"
        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            if refresh_access_token():
                headers["Authorization"] = f"Bearer {session['access_token']}"
                response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json().get("QueryResponse", {}).get(entity, [])
        return []

    invoices = run_query("Invoice")
    expenses = run_query("Purchase")

    print("Invoices fetched:", invoices)
    print("Expenses fetched:", expenses)

    revenue = sum(inv.get("TotalAmt", 0) for inv in invoices)
    cost = sum(exp.get("TotalAmt", 0) for exp in expenses)

    net = revenue - cost
    forecast = net / len(invoices) if invoices else 0

    session["forecast"] = round(forecast, 2)
    session["revenue"] = round(revenue, 2)
    session["cost"] = round(cost, 2)
    session["invoice_count"] = len(invoices)

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
