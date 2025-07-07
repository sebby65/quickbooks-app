from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY")  # set this in your environment

@app.route("/")
def home():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    token = request.form.get("g-recaptcha-response")

    if not token:
        return "reCAPTCHA token missing", 400

    # Verify with Google
    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": token
    }
    resp = requests.post(verify_url, data=payload)
    result = resp.json()

    if result.get("success") and result.get("score", 0) > 0.5:
        return "Form submission successful!"
    else:
        return "reCAPTCHA failed. Try again.", 400

if __name__ == "__main__":
    app.run(debug=True)


