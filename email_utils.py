# email_utils.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

def send_email_report(to_email, csv_data, subject="Your Clariqor Forecast Report"):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText("Attached is your latest financial forecast from Clariqor.", "plain"))

    attachment = MIMEApplication(csv_data, Name="forecast.csv")
    attachment["Content-Disposition"] = 'attachment; filename="forecast.csv"'
    msg.attach(attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
