import pandas as pd
from prophet import Prophet
from datetime import datetime

def transform_qb_to_df(qb_data):
    def extract_rows(rows, data):
        for row in rows:
            if 'ColData' in row:
                try:
                    label = row['ColData'][0].get('value')
                    amount = row['ColData'][1].get('value')
                    amount = float(amount.replace(',', '')) if amount else 0.0
                    # Fake a date for now based on order of entries
                    data.append({'label': label, 'amount': amount})
                except Exception as e:
                    print(f"Row parsing error: {e} — {row}")
            elif 'Rows' in row:
                extract_rows(row['Rows'].get('Row', []), data)

    all_rows = qb_data.get('Rows', {}).get('Row', [])
    data = []
    extract_rows(all_rows, data)

    if not data:
        raise ValueError("No usable data found in QuickBooks P&L report.")

    df = pd.DataFrame(data)
    df['date'] = pd.date_range(end=datetime.today(), periods=len(df), freq='M')
    df = df[['date', 'amount']]
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
