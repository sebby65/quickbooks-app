import os
import json
import requests
from flask import Flask, redirect, request, session, render_template, jsonify
from intuitlib.client import AuthClient
from intuitlib.exceptions import AuthClientError
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from prophet import Prophet
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Initialize AuthClient for QuickBooks
auth_client = AuthClient(
    client_id=os.getenv("QB_CLIENT_ID"),
    client_secret=os.getenv("QB_CLIENT_SECRET"),
    environment=os.getenv("QB_ENVIRONMENT", "production"),
    redirect_uri=os.getenv("QB_REDIRECT_URI")
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/connect")
def connect():
    auth_url = auth_client.get_authorization_url([
        "com.intuit.quickbooks.accounting"]
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    realm_id = request.args.get("realmId")

    try:
        auth_client.get_bearer_token(code, realm_id=realm_id)
        session["realm_id"] = realm_id
        session["access_token"] = auth_client.access_token
        session["refresh_token"] = auth_client.refresh_token
    except AuthClientError as e:
        return jsonify(e.response), 400

    return redirect("/")

@app.route("/forecast", methods=["POST"])
def forecast():
    if "access_token" not in session:
        return "Unauthorized", 401

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=session["refresh_token"],
        company_id=session["realm_id"]
    )

    invoices = Invoice.all(qb=client)

    data = [{
        "ds": inv.TxnDate,
        "y": float(inv.TotalAmt)
    } for inv in invoices if hasattr(inv, 'TxnDate') and hasattr(inv, 'TotalAmt')]

    if not data:
        return "No valid invoice data found.", 400

    df = pd.DataFrame(data)
    model = Prophet()
    model.fit(df)

    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    result = forecast[['ds', 'yhat']].tail(30).to_dict(orient='records')
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
