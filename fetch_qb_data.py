# fetch_qb_data.py
import os
import requests
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from quickbooks import QuickBooks

load_dotenv()

def get_qb_client():
    auth_client = AuthClient(
        client_id=os.getenv("QB_CLIENT_ID"),
        client_secret=os.getenv("QB_CLIENT_SECRET"),
        access_token=os.getenv("QB_ACCESS_TOKEN"),
        refresh_token=os.getenv("QB_REFRESH_TOKEN"),
        realm_id = os.getenv("QB_REALM_ID"),
        redirect_uri=os.getenv("QB_REDIRECT_URI"),
        environment=os.getenv("QB_ENVIRONMENT", "sandbox")
    )
    return QuickBooks(auth_client=auth_client, company_id=os.getenv("QB_REALM"))

def fetch_profit_and_loss(start_date="2024-01-01", end_date="2024-12-31"):
    client = get_qb_client()
    if os.getenv("QB_ENVIRONMENT") == "sandbox":
        base_url = "https://sandbox-quickbooks.api.intuit.com"
    else:
        base_url = "https://quickbooks.api.intuit.com"
  # e.g. https://sandbox-quickbooks.api.intuit.com
    company_id = client.company_id
    url = f"{base_url}/v3/company/{company_id}/reports/ProfitAndLoss"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "summarize_column_by": "Month",
        "minorversion": "65",
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {client.auth_client.access_token}"
    }

    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("❌ Error fetching P&L:", e)
        return None


