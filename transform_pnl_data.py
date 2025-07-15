import pandas as pd
from datetime import datetime
from prophet import Prophet

def transform_qb_to_df(qb_data):
    def extract(rows, data, label_type):
        for r in rows:
            if 'ColData' in r and label_type:
                try:
                    amt = float(r['ColData'][1]['value'].replace(',', '')) if r['ColData'][1]['value'] else 0.0
                    data.append({'ds': None, label_type: amt})
                except:
                    pass
            elif 'Rows' in r:
                extract(r['Rows']['Row'], data, label_type)

    # Extract income
    income = []
    extract(qb_data.get('Rows', {}).get('Row', []), income, 'income')
    # Fetch purchases for expenses here (or integrate if using fetch_purchase)
    # For now, treat negative of income list if no purchases table
    df = pd.DataFrame(income)
    if df.empty:
        raise ValueError("No usable income data in P&L report.")

    df['ds'] = pd.date_range(end=datetime.today(), periods=len(df), freq='M')
    df['y'] = df['income']
    return df[['ds', 'y']]

def generate_forecast(df):
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=12, freq='M')
    forecast = model.predict(future)[['ds', 'yhat']].rename(columns={'yhat': 'forecast'})
    forecast['forecast'] = forecast['forecast'].round(2)
    return forecast
