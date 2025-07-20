import os
import requests
from flask import Flask, redirect, request, jsonify
from datetime import datetime
import base64

app = Flask(__name__)

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")  # Make sure this is fixed in .env

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://quickbooks-app-3.onrender.com/callback")
ON_RENDER = os.getenv("RENDER", "false").lower() == "true"

def save_refresh_token(token):
    if ON_RENDER:
        return
    lines = []
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            lines = f.readlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("QB_REFRESH_TOKEN="):
            lines[i] = f"QB_REFRESH_TOKEN={token}\n"
            updated = True
    if not updated:
        lines.append(f"QB_REFRESH_TOKEN={token}\n")
    with open(".env", "w") as f:
        f.writelines(lines)

def get_access_token():
    global REFRESH_TOKEN
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + base64.b64encode(creds).decode("utf-8"),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    response = requests.post(TOKEN_URL, headers=headers, data=payload)
    if response.status_code != 200:
        print("QuickBooks token error:", response.text)
        return None
    data = response.json()
    REFRESH_TOKEN = data.get("refresh_token", REFRESH_TOKEN)
    save_refresh_token(REFRESH_TOKEN)
    return data["access_token"]

def fetch_pnl_report():
    """Fetch Profit & Loss report and parse real QuickBooks data."""
    token = get_access_token()
    if not token:
        return [{"error": "Could not authenticate with QuickBooks"}]

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        return [{"error": f"QuickBooks fetch failed: {response.status_code}"}]

    data = response.json()
    rows = data.get("Rows", {}).get("Row", [])
    parsed = []

    # Extract revenue, expenses, net income per month
    for row in rows:
        if row.get("type") == "Section":
            for sub in row.get("Rows", {}).get("Row", []):
                cells = sub.get("ColData", [])
                if len(cells) >= 2:
                    month = cells[0].get("value", "Unknown")
                    amount = float(cells[1].get("value", "0"))
                    parsed.append({"Month": month, "NetIncome": amount})

    return parsed or [{"message": "No P&L data found"}]

@app.route("/")
def home():
    return "QuickBooks App Running!"

@app.route("/connect")
def connect():
    auth_url = (
        f"https://appcenter.intuit.com/connect/oauth2?"
        f"client_id={CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting"
        f"&redirect_uri={REDIRECT_URI}&state=secureRandomState"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code parameter!", 400
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + base64.b64encode(creds).decode("utf-8"),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    response = requests.post(TOKEN_URL, headers=headers, data=payload)
    if response.status_code != 200:
        return f"OAuth exchange failed: {response.text}", 400
    data = response.json()
    global REFRESH_TOKEN
    REFRESH_TOKEN = data.get("refresh_token", REFRESH_TOKEN)
    save_refresh_token(REFRESH_TOKEN)
    return "QuickBooks connected successfully!"

@app.route("/pnl")
def pnl_route():
    return jsonify(fetch_pnl_report())

@app.route("/forecast")
def forecast_route():
    return "Forecast page (to be implemented)."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
