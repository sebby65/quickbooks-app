from quickbooks.reports.profit_and_loss import ProfitAndLoss

def fetch_qb_data(client, realm_id):
    report = ProfitAndLoss()
    return report.get(client)



