def fetch_profit_and_loss():
    # Mocking a P&L report structure that QuickBooks might return
    return {
        "Rows": {
            "Row": [
                {"ColData": [{"value": "2023-01-01"}, {"value": "1050.75"}]},
                {"ColData": [{"value": "2023-02-01"}, {"value": "1102.00"}]},
                {"ColData": [{"value": "2023-03-01"}, {"value": "1133.25"}]},
                {"ColData": [{"value": "2023-04-01"}, {"value": "1201.33"}]},
                {"ColData": [{"value": "2023-05-01"}, {"value": "1222.41"}]},
                {"ColData": [{"value": "2023-06-01"}, {"value": "1250.99"}]},
                {"ColData": [{"value": "2023-07-01"}, {"value": "1288.75"}]},
                {"ColData": [{"value": "2023-08-01"}, {"value": "1305.00"}]},
                {"ColData": [{"value": "2023-09-01"}, {"value": "1352.20"}]},
                {"ColData": [{"value": "2023-10-01"}, {"value": "1403.00"}]},
                {"ColData": [{"value": "2023-11-01"}, {"value": "1425.85"}]},
                {"ColData": [{"value": "2023-12-01"}, {"value": "1450.00"}]}
            ]
        }
    }
