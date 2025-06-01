import os
from flask import Flask, jsonify
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token

app = Flask(__name__)

# Prendi gli endpoint da variabili d'ambiente
FORMATTER_URL = os.environ.get("FORMATTER_URL")
ANONYMIZER_URL = os.environ.get("ANONYMIZER_URL")

def authenticated_request(url):
    audience = url
    token = id_token.fetch_id_token(Request(), audience)
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=5)
    return resp.text, resp.status_code

@app.route("/")
def root():
    return "Orchestratore online!"

@app.route("/test-formatter")
def test_formatter():
    if not FORMATTER_URL:
        return "FORMATTER_URL not set", 500
    try:
        msg, status = authenticated_request(FORMATTER_URL)
        return jsonify({"service": "formatter", "response": msg}), status
    except Exception as e:
        return str(e), 500

@app.route("/test-anonymizer")
def test_anonymizer():
    if not ANONYMIZER_URL:
        return "ANONYMIZER_URL not set", 500
    try:
        msg, status = authenticated_request(ANONYMIZER_URL)
        return jsonify({"service": "anonymizer", "response": msg}), status
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)