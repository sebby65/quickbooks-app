from flask import Flask, render_template
from transform_pnl_data import transform_qb_to_df, generate_forecast
import json

app = Flask(__name__)

# Sample hardcoded QuickBooks JSON structure — replace this with real fetch logic later
qb_sample_data = {
    "Rows": {
        "Row": [
            {"ColData": [{"value": "2024-01-01"}, {"value": "1000"}]},
            {"ColData": [{"value": "2024-02-01"}, {"value": "1100"}]},
            {"ColData": [{"value": "2024-03-01"}, {"value": "1200"}]},
            {"ColData": [{"value": "2024-04-01"}, {"value": "1250"}]},
        ]
    }
}

@app.route('/dashboard')
def dashboard():
    df = transform_qb_to_df(qb_sample_data)
    forecast_df = generate_forecast(df)
    forecast_data = forecast_df.to_dict(orient='records')
    return render_template('financial_dashboard.html', forecast_data=json.dumps(forecast_data))

if __name__ == '__main__':
    app.run(debug=True)
