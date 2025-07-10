import os
import json
import requests
import pandas as pd
from flask import Flask, request, redirect, render_template, session, url_for
from dotenv import load_dotenv
from flask_mail import Mail, Message
from prophet import Prophet
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

mail_settings = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': os.getenv('EMAIL_USER'),
    'MAIL_PASSWORD': os.getenv('EMAIL_PASS')
}
app.config.update(mail_settings)
mail = Mail(app)

auth_client = AuthClient(
    client_id=os.getenv('CLIENT_ID'),
    client_secret=os.getenv('CLIENT_SECRET'),
    environment='production',
    redirect_uri=os.getenv('REDIRECT_URI')
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect')
def connect():
    url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    print("Generated AUTH URL:", url)
    return redirect(url)

@app.route('/callback')
def callback():
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    session['realm_id'] = realm_id
    auth_client.get_bearer_token(auth_code)
    session['access_token'] = auth_client.access_token
    return redirect(url_for('index'))

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        access_token = session.get('access_token')
        realm_id = session.get('realm_id')

        if not access_token or not realm_id:
            return 'Unauthorized', 401

        client = QuickBooks(
            auth_client=auth_client,
            refresh_token=auth_client.refresh_token,
            company_id=realm_id
        )

        invoices = Invoice.all(qb=client)
        data = []
        for invoice in invoices:
            if hasattr(invoice, 'TxnDate') and hasattr(invoice, 'TotalAmt'):
                data.append({"date": invoice.TxnDate, "amount": invoice.TotalAmt})

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.groupby('date').sum().reset_index()
        df.columns = ['ds', 'y']

        model = Prophet()
        model.fit(df)

        future = model.make_future_dataframe(periods=30)
        forecast = model.predict(future)

        forecast_data = forecast[['ds', 'yhat']].tail(30).to_dict(orient='records')
        return json.dumps(forecast_data)

    except Exception as e:
        print("Error during forecast:", str(e))
        return f"Forecasting failed: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
