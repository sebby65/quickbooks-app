from flask import Flask, render_template
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

# Home page
@app.route('/')
def home():
    return render_template('financial_dashboard.html', forecast=[])

# Forecast generation route
@app.route('/forecast')
def forecast():
    # Example QuickBooks-style data for testing
    qb_data = {
        "Rows": {
            "Row": [
                {"ColData": [{"value": "2024-01-01"}, {"value": "1000"}]},
                {"ColData": [{"value": "2024-02-01"}, {"value": "1100"}]},
                {"ColData": [{"value": "2024-03-01"}, {"value": "1200"}]},
            ]
        }
    }

    # Transform and forecast
    df = transform_qb_to_df(qb_data)
    forecast_df = generate_forecast(df)
    forecast_json = forecast_df.to_dict(orient='records')

    return render_template('financial_dashboard.html', forecast=forecast_json)

if __name__ == '__main__':
    app.run(debug=True)
