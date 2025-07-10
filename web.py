import os
import json
from flask import Flask, redirect, request, render_template, session, jsonify
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from requests_oauthlib import OAuth2Session
from flask_session import Session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect')
def connect():
    auth_client = AuthClient(
        client_id=os.environ.get("QB_CLIENT_ID"),
        client_secret=os.environ.get("QB_CLIENT_SECRET"),
        environment=os.environ.get("QB_ENVIRONMENT"),
        redirect_uri=os.environ.get("REDIRECT_URI")
    )
    
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    session['auth_client'] = auth_client.__dict__
    print(f"Generated AUTH URL: {auth_url}")
    return redirect(auth_url)

@app.route('/callback')
def callback():
    auth_client = AuthClient(
        client_id=os.environ.get("QB_CLIENT_ID"),
        client_secret=os.environ.get("QB_CLIENT_SECRET"),
        environment=os.environ.get("QB_ENVIRONMENT"),
        redirect_uri=os.environ.get("REDIRECT_URI")
    )

    auth_client.__dict__.update(session['auth_client'])

    try:
        auth_client.get_bearer_token(request.args.get('code'), realm_id=request.args.get('realmId'))
        session['access_token'] = auth_client.access_token
        session['realm_id'] = request.args.get('realmId')
        print("Access token acquired")
        return redirect('/')
    except AuthClientError as e:
        return f"Callback error: {e}"

@app.route('/forecast', methods=['POST'])
def forecast():
    if 'access_token' not in session or 'realm_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Placeholder logic for financial forecasting
        return jsonify({"message": "Forecasting complete."})
    except Exception as e:
        return jsonify({"error": f"Forecasting failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
