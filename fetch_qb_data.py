import requests

def fetch_profit_and_loss(access_token, realm_id):
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/reports/ProfitAndLoss?minorversion=65"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    return response.json()
