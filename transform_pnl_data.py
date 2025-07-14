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
            except (IndexError, KeyError, ValueError) as e:
                print(f"Row skipped due to parsing error: {e} — {row}")
                continue
        else:
            print(f"No ColData in row: {row}")

    if not data:
        raise ValueError("No usable data found in QuickBooks P&L report.")

    df = pd.DataFrame(data)
    if 'date' not in df.columns or 'amount' not in df.columns:
        raise ValueError(f"Unexpected dataframe structure: {df.head()}")

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
