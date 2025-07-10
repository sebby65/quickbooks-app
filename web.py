import os
from flask import Flask, request, redirect, session, render_template
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import requests
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# OAuth credentials
client_id = os.getenv("QB_CLIENT_ID")
client_secret = os.getenv("QB_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")
environment = os.getenv("QB_ENVIRONMENT", "sandbox")

# Setup Intuit auth client
auth_client = AuthClient(
    client_id=client_id,
    client_secret=client_secret,
    environment=environment,
    redirect_uri=redirect_uri
)

@app.route("/")
def index():
    error = session.pop("forecast_error", None)
    plot_url = session.pop("plot_url", None)
    return render_template("index.html", error=error, plot_url=plot_url)

@app.route("/connect")
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    realm_id = request.args.get("realmId")
    if not code or not realm_id:
        return "Missing code or realmId", 400

    try:
        auth_client.get_bearer_token(code)
        session["access_token"] = auth_client.access_token
        session["realm_id"] = realm_id
        return redirect("/")
    except Exception as e:
        return f"Auth failed: {str(e)}", 500

@app.route("/forecast", methods=["POST"])
def forecast():
    access_token = session.get("access_token")
    realm_id = session.get("realm_id")
    if not access_token or not realm_id:
        session["forecast_error"] = "Missing access token or realm ID."
        return redirect("/")

    url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/text"
    }
    query = "SELECT TxnDate, TotalAmt FROM Invoice"

    try:
        response = requests.post(url, headers=headers, data=query)
        response.raise_for_status()
        invoices = response.json()["QueryResponse"]["Invoice"]
        df = pd.DataFrame(invoices)
        df["TxnDate"] = pd.to_datetime(df["TxnDate"])
        df = df.sort_values("TxnDate")
        df = df.groupby("TxnDate").sum().reset_index()

        # Plotting
        plt.figure(figsize=(10, 5))
        plt.plot(df["TxnDate"], df["TotalAmt"], marker="o")
        plt.title("Financial Forecast")
        plt.xlabel("Date")
        plt.ylabel("Total Amount")
        plt.grid(True)
        plt.tight_layout()

        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        plot_url = base64.b64encode(img.read()).decode("utf-8")
        session["plot_url"] = plot_url
    except Exception as e:
        session["forecast_error"] = str(e)

    return redirect("/")
