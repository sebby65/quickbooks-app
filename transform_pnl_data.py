import pandas as pd
from datetime import datetime
from prophet import Prophet

def transform_qb_to_df(qb_data):
    def extract_rows(rows, data):
        for row in rows:
            if 'ColData' in row:
                try:
                    label = row['ColData'][0].get('value')
                    amount = row['ColData'][1].get('value')
                    amount = float(amount.replace(',', '')) if amount else 0.0
                    data.append({'label': label, 'amount': amount})
                except Exception as e:
                    continue
            elif 'Rows' in row:
                extract_rows(row['Rows'].get('Row', []), data)

    all_rows = qb_data.get('Rows', {}).get('Row', [])
    data = []
    extract_rows(all_rows, data)

    if not data:
        raise ValueError("No usable data found in QuickBooks P&L report.")

    df = pd.DataFrame(data)
    df['date'] = pd.date_range(end=datetime.today(), periods=len(df), freq='M')
    return df[['date', 'amount']]

def generate_forecast(df):
    df = df.rename(columns={'date': 'ds', 'amount': 'y'})
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=12, freq='M')
    forecast = model.predict(future)
    forecast = forecast[['ds', 'yhat']].rename(columns={'ds': 'date', 'yhat': 'forecast'})
    forecast['forecast'] = forecast['forecast'].round(2)
    return forecast
