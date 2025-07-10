import os
import json
import pandas as pd
from flask import Flask, render_template_string, redirect, request, session
from prophet import Prophet
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# OAuth2 Config
auth_client = AuthClient(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    environment="production",
    redirect_uri=os.getenv("REDIRECT_URI")
)

qbo_client = None

@app.route("/")
def index():
    return render_template_string('''
        <h1><b>Financial Forecast Dashboard</b></h1>
        <form action="/forecast" method="post">
            <button type="submit">Generate Forecast</button>
        </form>
        {% if error %}<p><b>Forecasting failed:</b> {{ error }}</p>{% endif %}
        {% if forecast_url %}<iframe src="{{ forecast_url }}" width="100%" height="600"></iframe>{% endif %}
        <p>{{ status }}</p>
    ''',
    status="Connected to QuickBooks" if qbo_client else "Not connected to QuickBooks",
    error=request.args.get("error"),
    forecast_url=request.args.get("forecast"))

@app.route("/connect")
def connect():
    url = auth_client.get_authorization_url(["com.intuit.quickbooks.accounting"])
    return redirect(url)

@app.route("/callback")
def callback():
    auth_code = request.args.get("code")
    realm_id = request.args.get("realmId")
    session["realm_id"] = realm_id

    auth_client.get_bearer_token(auth_code)
    global qbo_client
    qbo_client = QuickBooks(
        auth_client=auth_client,
        refresh_token=auth_client.refresh_token,
        company_id=realm_id
    )
    return redirect("/")

@app.route("/forecast", methods=["POST"])
def forecast():
    try:
        if not qbo_client:
            return redirect("/connect")

        # Get Invoices (this could be updated for other transaction types)
        invoices = Invoice.all(qbo=qbo_client)
        data = []
        for invoice in invoices:
            if hasattr(invoice, 'TxnDate') and hasattr(invoice, 'TotalAmt'):
                data.append({"date": invoice.TxnDate, "amount": invoice.TotalAmt})

        if not data:
            raise ValueError("No invoice data returned from QuickBooks.")

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.groupby('date').sum().reset_index()
        df = df.rename(columns={"date": "ds", "amount": "y"})

        model = Prophet()
        model.fit(df)
        future = model.make_future_dataframe(periods=30)
        forecast = model.predict(future)

        fig = model.plot(forecast)
        fig.savefig("static/forecast.png")

        return redirect("/?forecast=/static/forecast.png")

    except Exception as e:
        return redirect(f"/?error={str(e)}")

if __name__ == "__main__":
    app.run(debug=True)
