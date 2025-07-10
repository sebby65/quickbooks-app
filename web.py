from flask import Flask, render_template, jsonify
from fetch_qb_data import fetch_profit_and_loss
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template('financial_dashboard.html')

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = fetch_profit_and_loss()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        forecast_data = forecast_df.to_dict(orient='records')
        return jsonify(forecast_data)
    except Exception as e:
        return jsonify({'error': f'Forecasting failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
