from flask import Flask, render_template, request, jsonify
from transform_pnl_data import transform_qb_to_df, generate_forecast
from fetch_qb_data import fetch_profit_and_loss
import plotly.graph_objs as go
import plotly.io as pio

app = Flask(__name__)

# Home route
@app.route('/')
def dashboard():
    return render_template('financial_dashboard.html')

# Forecast route (POSTs raw QB data JSON and returns forecast)
@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        qb_data = request.get_json()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)
        return jsonify(forecast_df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({'error': f'Forecasting failed: {str(e)}'}), 500

# QuickBooks data fetch route
@app.route('/get_qb_data', methods=['GET'])
def get_qb_data():
    try:
        qb_data = fetch_profit_and_loss()
        return jsonify(qb_data)
    except Exception as e:
        return jsonify({'error': f'QuickBooks fetch failed: {str(e)}'}), 500

# Optional chart rendering route (if you want server-side plot images later)
@app.route('/plot')
def plot():
    try:
        qb_data = fetch_profit_and_loss()
        df = transform_qb_to_df(qb_data)
        forecast_df = generate_forecast(df)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=forecast_df['date'],
            y=forecast_df['forecast'],
            mode='lines+markers',
            name='Forecast'
        ))

        fig.update_layout(title='Financial Forecast',
                          xaxis_title='Date',
                          yaxis_title='Forecast Amount ($)',
                          template='plotly_white')

        graph_html = pio.to_html(fig, full_html=False)
        return graph_html

    except Exception as e:
        return f"<h3>Plot failed: {str(e)}</h3>", 500

if __name__ == '__main__':
    app.run(debug=True)
