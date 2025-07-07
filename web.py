from flask import Flask, render_template, request, redirect, flash
from flask_mail import Mail, Message
import os

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

    if not name or not email:
        flash("Name and email are required.")
        return redirect("/")

    try:
        msg = Message(
            subject="New Payment Form Submission",
            sender=os.getenv("EMAIL_USER"),
            recipients=[os.getenv("EMAIL_RECEIVER")],
            body=f"Name: {name}\nEmail: {email}"
        )
        mail.send(msg)
        return redirect("/thankyou")
    except Exception as e:
        print(f"Email failed to send: {e}")
        return "An error occurred. Please try again later.", 500

@app.route("/thankyou")
def thankyou():
    return "<h2>Thank you for your submission. We'll be in touch shortly.</h2>"

if __name__ == "__main__":
    app.run(debug=True)
