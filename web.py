from flask import Flask, render_template, request, redirect, jsonify
from flask_mail import Mail, Message
from transform_pnl_data import transform_qb_to_df, generate_forecast
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Flask-Mail configuration
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

@app.route("/forecast", methods=["POST"])
def forecast():
    qb_data = request.get_json()
    df = transform_qb_to_df(qb_data)
    forecast = generate_forecast(df)
    return jsonify(forecast.to_dict(orient='records'))

if __name__ == "__main__":
    app.run(debug=True)
