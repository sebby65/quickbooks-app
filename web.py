from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    token = request.form.get("payment_token")
    if not token:
        return "Token not received", 400

    print("Received payment token:", token)
    return "Payment token received. Processing will happen server-side."

if __name__ == "__main__":
    app.run(debug=True)
