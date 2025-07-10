from flask import Flask, render_template, request, jsonify
import pandas as pd
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('financial_dashboard.html')

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = request.get_json()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        forecast_json = forecast_df.to_dict(orient='records')
        return jsonify(forecast_json)
    except Exception as e:
        return jsonify({'error': f'Forecasting failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
