from flask import Flask, request, jsonify
from transform_pnl_data import transform_qb_to_df, generate_forecast

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return 'Financial Forecast App is running.'

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = request.get_json()
        df = transform_qb_to_df(qb_data)
        forecast = generate_forecast(df)
        return jsonify(forecast.to_dict(orient='records'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
