from flask import Flask, render_template, request, redirect, send_from_directory
from flask_mail import Mail, Message
import os
from fetch_qb_data import fetch_profit_and_loss
from transform_pnl_data.py import transform_qb_to_df
from financial_summary import run_summary_and_dashboard

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Flask-Mail config
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv("EMAIL_USER"),
    MAIL_PASSWORD=os.getenv("EMAIL_PASS")
)

mail = Mail(app)

@app.route("/")
def home():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name")
    email = request.form.get("email")

    msg = Message(
        subject="New Payment Form Submission",
        sender=os.getenv("EMAIL_USER"),
        recipients=[os.getenv("EMAIL_RECEIVER")],
        body=f"Name: {name}\nEmail: {email}"
    )
    mail.send(msg)

    return redirect("/")

@app.route("/forecast")
def forecast():
    try:
        # Pull QB data and transform it
        json_data = fetch_profit_and_loss()
        df = transform_qb_to_df(json_data)

        # Run forecast and generate dashboard
        run_summary_and_dashboard(df)

        # Serve the generated dashboard file
        return send_from_directory(directory="static", path="financial_dashboard.html")
    except Exception as e:
        return f"Error during forecast: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
