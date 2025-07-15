import requests

def fetch_qb_data(auth_client, realm_id):
    access_token = auth_client.access_token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/reports/ProfitAndLoss?date_macro=LastYear"

    response = requests.get(url, headers=headers)
    print("QuickBooks API Response:", response.text)  # <-- Add this

    return response.json()
