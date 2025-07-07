import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet
import openai
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def forecast_cash_flow(df):
    df_prophet = df.rename(columns={"Month": "ds", "Deposits": "y"})[["ds", "y"]]
    df_prophet["ds"] = pd.to_datetime(df_prophet["ds"])

    m = Prophet()
    m.fit(df_prophet)

    future = m.make_future_dataframe(periods=3, freq='M')
    forecast = m.predict(future)

    fig = m.plot(forecast)
    plt.title("Cash Flow Forecast")
    plt.xlabel("Date")
    plt.ylabel("Deposits")
    plt.savefig("financial_dashboard.html")
    plt.close()
    return forecast


def generate_financial_summary(df):
    try:
        prompt = f"""
        Here is a table of monthly deposits and payables:

        {df.to_string(index=False)}

        Summarize the financial performance and generate a simple forecast for the next 90 days in a way that anyone, including a non-finance person, can understand.
        """

        resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial analyst summarizing data for small businesses."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )

        summary = resp["choices"][0]["message"]["content"]
        print("\n--- Summary ---\n", summary)

        os.makedirs("summaries", exist_ok=True)
        with open("summaries/Forecasted_Summary.txt", "w") as f:
            f.write(summary)

    except Exception as e:
        print(f"❌ Error generating summary: {e}")


def run_summary_and_dashboard(df):
    forecast = forecast_cash_flow(df)
    generate_financial_summary(df)


if __name__ == "__main__":
    print("📊 Running financial summary...")

    try:
        df = pd.read_csv("transformed_data.csv")
        run_summary_and_dashboard(df)
    except Exception as e:
        print(f"❌ Error loading data or running analysis: {e}")
