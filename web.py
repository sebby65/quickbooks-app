from flask import Flask, render_template, jsonify, request
import json
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

@app.route('/')
def home():
    return 'Clariqor Financial Forecasting App'

@app.route("/dashboard")
def dashboard():
    try:
        forecast_df = pd.read_csv('forecast_output.csv')
        forecast_json = forecast_df.to_dict(orient='records')
    except Exception:
        forecast_json = []

    return render_template("financial_dashboard.html", forecast=forecast_json)


@app.route('/api/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = request.get_json()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        result = forecast_df.to_dict(orient='records')
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
