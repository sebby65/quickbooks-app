from flask import Flask, render_template
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

# Home page
@app.route('/')
def home():
    return render_template('financial_dashboard.html', forecast=[])

# Forecast generation route
@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = request.get_json()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)

        data = forecast_df.to_dict(orient='records')
        return jsonify(data)

    except Exception as e:
        return jsonify({'error': f'Forecasting failed: {str(e)}'}), 500


    # Transform and forecast
    df = transform_qb_to_df(qb_data)
    forecast_df = generate_forecast(df)
    forecast_json = forecast_df.to_dict(orient='records')

    return render_template('financial_dashboard.html', forecast=forecast_json)

if __name__ == '__main__':
    app.run(debug=True)
