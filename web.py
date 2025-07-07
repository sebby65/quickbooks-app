from flask import Flask, render_template, request
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
@app.route("/submit", methods=["POST"])
def submit():
    token = request.form.get("payment_token")
    if not token:
        return "Token not received", 400

    # Log or forward the token to your payment processor
    print("Received payment token:", token)

    return "Payment token received. Processing will happen server-side."

        # Get form inputs
        name = request.form.get("name")
        email = request.form.get("email")
        token = request.form.get("recaptcha-token")

        # Verify reCAPTCHA
        verify_url = "https://www.google.com/recaptcha/api/siteverify"
        payload = {
            "secret": RECAPTCHA_SECRET_KEY,
            "response": token
        }

        response = requests.post(verify_url, data=payload)
        result = response.json()

        if not result.get("success") or result.get("score", 0) < 0.5:
            return "reCAPTCHA failed. Please try again.", 400

        # 🚧 Payment token logic will go here
        print(f"Received from {name} ({email})")

        return "Payment form submitted successfully!"

    return render_template("form.html")

if __name__ == "__main__":
    app.run(debug=True)
