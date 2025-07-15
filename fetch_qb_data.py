def fetch_qb_data(client, realm_id):
    # Hit the Profit and Loss report endpoint manually
    return client.request(
        "GET",
        f"/v3/company/{realm_id}/reports/ProfitAndLoss"
    )




