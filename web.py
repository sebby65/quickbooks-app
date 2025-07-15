import os
from flask import Flask, render_template, request, redirect, send_file
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
import pandas as pd
from prophet import Prophet
from io import BytesIO
from dotenv import load_dotenv
from transform_pnl_data import transform_qb_to_df
from email_utils import send_forecast_email

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

CLIENT_ID = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ENVIRONMENT = os.getenv("QB_ENVIRONMENT")
REALM_ID = os.getenv("QB_REALM")

try:
    auth_client = AuthClient(CLIENT_ID, CLIENT_SECRET, ENVIRONMENT, REDIRECT_URI)
except Exception as e:
    print("Error initializing AuthClient:", e)
    raise

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/connect")
def connect():
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return redirect(auth_url)

@app.route("/callback")
def callback():
    auth_client.get_bearer_token(request.args.get('code'))
    return redirect("/")

@app.route("/forecast", methods=["POST"])
def forecast():
    months = int(request.args.get("range", 12))
    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=auth_client.refresh_token,
        company_id=REALM_ID,
    )
    pnl = ProfitAndLoss()
    pnl_data = pnl.get(client)
    df = transform_qb_to_df(pnl_data)
    df = df.sort_values("ds").tail(months)

    model = Prophet()
    model.fit(df.rename(columns={"ds": "ds", "y": "y"}))
    future = model.make_future_dataframe(periods=months, freq="M")
    forecast = model.predict(future)

    merged = pd.merge(df, forecast[["ds", "yhat"]], on="ds", how="left")
    merged.rename(columns={"yhat": "forecast"}, inplace=True)
    app.config["forecast_df"] = merged

    chart_data = merged.to_dict("records")
    return render_template("index.html", chart_data=chart_data)

@app.route("/download")
def download():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast to download", 400
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="forecast.csv")

@app.route("/email", methods=["POST"])
def email():
    df = app.config.get("forecast_df")
    if df is None:
        return "No forecast to email", 400
    to_email = request.form.get("email", os.getenv("EMAIL_RECEIVER"))
    status = send_forecast_email(to_email, df)
    return render_template("index.html", email_status=status)

if __name__ == "__main__":
    app.run(debug=True)
