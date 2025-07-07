from flask import Flask, render_template, request, redirect
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

    msg = Message(
        subject="New Payment Form Submission",
        sender=os.getenv("EMAIL_USER"),
        recipients=[os.getenv("EMAIL_RECEIVER")],
        body=f"Name: {name}\nEmail: {email}"
    )
    mail.send(msg)

    return redirect("/")  # Redirect to home or thank-you page

if __name__ == "__main__":
    app.run(debug=True)
