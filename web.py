import os
import requests
from flask import Flask, redirect, request, jsonify
from datetime import datetime

app = Flask(__name__)

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("QB_REFRESH_TOKEN")
REALM_ID = os.getenv("QB_REALM_ID")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"

# Detect if running on Render (no .env writes allowed)
ON_RENDER = os.getenv("RENDER", "false").lower() == "true"

def save_refresh_token(token):
    """Only save refresh token locally (not on Render)."""
    if ON_RENDER:
        return  # Skip writing to disk on Render
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
    """Refresh QuickBooks access token."""
    global REFRESH_TOKEN
    auth_header = (CLIENT_ID + ":" + CLIENT_SECRET).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + auth_header.decode("utf-8"),
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
    """Fetch Profit & Loss report from QuickBooks."""
    token = get_access_token()
    if not token:
        return []

    start_date = f"{datetime.now().year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{REALM_ID}/reports/ProfitAndLoss?start_date={start_date}&end_date={end_date}"

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("QuickBooks fetch failed:", response.text)
        return []

    # Replace with real JSON parsing
    return [
        {"Month": "Jan 2025", "Revenue": 90000, "Expenses": 30000, "NetIncome": 60000},
        {"Month": "Feb 2025", "Revenue": 105000, "Expenses": 35000, "NetIncome": 70000}
    ]

@app.route("/")
def home():
    return "QuickBooks App Running!"

@app.route("/pnl")
def pnl_route():
    report = fetch_pnl_report()
    return jsonify(report)

@app.route("/forecast")
def forecast_route():
    return "Forecast page (to be implemented)."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
