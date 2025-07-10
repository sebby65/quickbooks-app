# web.py
from flask import Flask, render_template, jsonify, redirect, request, session
from fetch_qb_data import fetch_profit_and_loss
from transform_pnl_data import transform_qb_to_df, generate_forecast
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "devsecret")

# Hardcoded redirect URI to prevent mismatch
auth_client = AuthClient(
    client_id=os.environ.get("QB_CLIENT_ID"),
    client_secret=os.environ.get("QB_CLIENT_SECRET"),
    redirect_uri="https://quickbooks-app-3.onrender.com/callback",
    environment="sandbox"
)

@app.route('/')
def dashboard():
    return render_template('financial_dashboard.html')

@app.route('/connect')
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    print("Generated AUTH URL:", auth_url)
    return redirect(auth_url)

@app.route('/callback')
def callback():
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')

    if not auth_code or not realm_id:
        print("Missing code or realm ID.")
        return "Missing authorization code or realm ID", 400

    try:
        print(f"Received code: {auth_code}, realm_id: {realm_id}")
        auth_client.get_bearer_token(auth_code)
        session['access_token'] = auth_client.access_token
        session['realm_id'] = realm_id
        print(f"Access token: {auth_client.access_token}")
        print(f"Session set: {dict(session)}")
    except Exception as e:
        print(f"Token exchange failed: {e}")
        return f"OAuth token error: {e}", 500

    return redirect('/')

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        access_token = session.get('access_token')
        realm_id = session.get('realm_id')

        if not access_token or not realm_id:
            return jsonify({'error': 'Not connected to QuickBooks'}), 401

        qb_data = fetch_profit_and_loss(access_token, realm_id)
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        forecast_data = forecast_df.to_dict(orient='records')
        return jsonify(forecast_data)
    except Exception as e:
        print(f"Forecasting error: {e}")
        return jsonify({'error': f'Forecasting failed: {str(e)}'}), 500

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True)
