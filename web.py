from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    token = request.form.get('g-recaptcha-response')
    secret_key = "6LeH6ncrAAAAGgRaZ8n3h-e9H8S2wk_5bGL53Jg"

    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    response = requests.post(verify_url, data={
        "secret": secret_key,
        "response": token
    })

    result = response.json()
    if not result.get("success"):
        return "Failed reCAPTCHA. Try again."

    return "Form successfully submitted!"

