import os
import uuid
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, redirect, request, render_template, session, jsonify
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from intuitlib.exceptions import AuthClientError
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from prophet import Prophet

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# Setup OAuth2
auth_client = AuthClient(
    client_id=os.getenv("QB_CLIENT_ID"),
    client_secret=os.getenv("QB_CLIENT_SECRET"),
    environment=os.getenv("QB_ENVIRONMENT"),
    redirect_uri=os.getenv("QB_REDIRECT_URI")
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/connect")
def connect():
    try:
        state = str(uuid.uuid4())
        session["state"] = state
        auth_url = auth_client.get_authorization_url([os.getenv("QB_SCOPE")], state)
        print("Generated AUTH URL:", auth_url)
        return redirect(auth_url)
    except AuthClientError as e:
        return f"Error generating auth URL: {str(e)}", 500

@app.route("/callback")
def callback():
    try:
        state = request.args.get("state")
        if state != session.get("state"):
            return "State mismatch. Possible CSRF detected.", 400

        auth_code = request.args.get("code")
        realm_id = request.args.get("realmId")
        session["realm_id"] = realm_id
        auth_client.get_bearer_token(auth_code)
        session["access_token"] = auth_client.access_token
        return redirect("/")
    except Exception as e:
        return f"Callback failed: {str(e)}", 500

@app.route("/forecast", methods=["POST"])
def forecast():
    try:
        if "access_token" not in session or "realm_id" not in session:
            return "Unauthorized", 401

        client = QuickBooks(
            auth_client=auth_client,
            refresh_token=auth_client.refresh_token,
            company_id=session["realm_id"]
        )

        invoices = Invoice.all(qb=client)
        if not invoices:
            return jsonify({"error": "No invoices found."}), 404

        data = [{
            "ds": inv.TxnDate.strftime("%Y-%m-%d"),
            "y": float(inv.TotalAmt)
        } for inv in invoices if inv.TxnDate and inv.TotalAmt]

        df = pd.DataFrame(data)
        df["ds"] = pd.to_datetime(df["ds"])

        model = Prophet()
        model.fit(df)
        future = model.make_future_dataframe(periods=30)
        forecast = model.predict(future)

        forecast_plot_path = "static/forecast.png"
        model.plot(forecast)
        plt.savefig(forecast_plot_path)
        plt.close()

        return jsonify({"message": "Forecast generated", "plot_url": forecast_plot_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
