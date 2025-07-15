import os
import smtplib
from email.message import EmailMessage
from io import StringIO

def send_forecast_email(to_email, df):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your Financial Forecast Report"
        msg["From"] = os.getenv("EMAIL_USER")
        msg["To"] = to_email
        msg.set_content("Please find the attached forecast report.")

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        msg.add_attachment(csv_buffer.getvalue(), filename="forecast.csv", subtype="csv", maintype="text")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
            smtp.send_message(msg)

        return "Email sent successfully."
    except Exception as e:
        return f"Email failed: {str(e)}"
