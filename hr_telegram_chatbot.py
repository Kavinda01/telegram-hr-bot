
import pandas as pd
import requests
from flask import Flask, request

app = Flask(__name__)

# Load HR Excel data
df = pd.read_excel("All_Staff_Leave_Entitlement2.xlsx", sheet_name="Sheet1")

# Replace with your actual Telegram Bot Token from @BotFather
import os
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Helper: find employee by EMP_NO or partial name
def find_employee(identifier):
    emp = df[df['EMP_NO'] == identifier]
    if emp.empty:
        emp = df[df['LNAME'].str.contains(identifier, case=False, na=False)]
    return emp.iloc[0] if not emp.empty else None

# Helper: process the incoming message and return a reply
def generate_reply(chat_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        return "❗ Please enter your EMP_NO or name followed by your question.\nExample: NMC7070 annual leave"

    emp_id = parts[0]
    message = " ".join(parts[1:]).lower()
    emp = find_employee(emp_id)

    if emp is None:
        return "❌ Employee not found. Please check your EMP_NO or name."

    if "annual leave" in message:
        return f"Hi {emp['LNAME']}, your annual leave entitlement is {emp['Annual Entitle']} days."
    elif "casual leave" in message:
        return f"Hi {emp['LNAME']}, your casual leave entitlement is {emp['Casual Entitle']} days."
    elif "join" in message or "appointment" in message:
        return f"Hi {emp['LNAME']}, you joined the company on {emp['FADAY'].date()}."
    else:
        return "🤖 Sorry, I didn't understand. Ask about 'annual leave', 'casual leave', or 'joining date'."

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    chat_id = data["message"]["chat"]["id"]
    message_text = data["message"]["text"]

    reply = generate_reply(chat_id, message_text)

    requests.post(TELEGRAM_API_URL, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "ok"

@app.route('/')
def home():
    return "✅ Telegram HR Chatbot is running."

if __name__ == '__main__':
    app.run(debug=True)
