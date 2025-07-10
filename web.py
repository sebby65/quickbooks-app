from flask import redirect, request, session
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

# Put this near the top
auth_client = AuthClient(
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_CLIENT_SECRET',
    redirect_uri='https://clariqor.com/callback',
    environment='production'
)

@app.route('/connect')
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return redirect(auth_url)

@app.route('/callback')
def callback():
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    session['realm_id'] = realm_id

    auth_client.get_bearer_token(auth_code)
    session['access_token'] = auth_client.access_token
    return redirect('/')
