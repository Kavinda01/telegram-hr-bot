# A Simple Flask-based Telegram HR Bot (without Excel)
# This bot answers common HR questions with fixed (dummy) responses

from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Get your token from environment variable or hardcode here (not recommended for production)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Predefined dummy answers for common HR questions
HR_FAQ = {
    "salary date": "Salary is paid on the 25th of every month.",
    "hr contact": "You can reach HR at hr@nawaloka.com or ext. 204.",
    "training schedule": "The next mandatory training is on May 3rd at 10:00 AM in Conference Room B.",
    "report issue": "To report an issue, please email support@nawaloka.com or call ext. 105.",
    "holiday list": "The upcoming public holiday is Vesak Day on May 23rd."
}

def get_response(message):
    message = message.lower()
    for key in HR_FAQ:
        if key in message:
            return HR_FAQ[key]
    return "I'm sorry, I didn't understand that. You can ask about salary date, HR contact, training schedule, etc."

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    chat_id = data["message"]["chat"]["id"]
    message_text = data["message"].get("text", "")

    reply = get_response(message_text)

    requests.post(TELEGRAM_API_URL, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "ok"

@app.route("/")
def home():
    return "✅ Telegram HR FAQ Bot is running."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)