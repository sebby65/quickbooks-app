import pandas as pd
from prophet import Prophet

def transform_qb_to_df(qb_data):
    rows = qb_data.get('Rows', {}).get('Row', [])
    data = []
    for row in rows:
        if 'ColData' in row:
            try:
                date = row['ColData'][0]['value']
                amount = row['ColData'][1]['value']
                amount = float(amount.replace(',', '')) if amount else 0.0
                data.append({'date': date, 'amount': amount})
            except (IndexError, KeyError, ValueError):
                continue

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df = df.dropna()
    df = df.groupby('date').sum().reset_index()
    return df

def generate_forecast(df):
    prophet_df = df.rename(columns={'date': 'ds', 'amount': 'y'})
    model = Prophet()
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=12, freq='M')
    forecast = model.predict(future)
    forecast = forecast[['ds', 'yhat']].rename(columns={'ds': 'date', 'yhat': 'forecast'})
    forecast['date'] = forecast['date'].dt.strftime('%Y-%m')
    forecast['forecast'] = forecast['forecast'].round(2)
    return forecast
