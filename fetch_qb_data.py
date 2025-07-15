import requests

def fetch_qb_data(auth_client, realm_id):
    access_token = auth_client.access_token
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/reports/ProfitAndLoss"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch P&L data: {response.status_code}, {response.text}")

    return response.json()
