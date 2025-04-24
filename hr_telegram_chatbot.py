# A Telegram HR Recruitment Bot with Resume Emailing, Confirmation Message, and Interview Scheduling

from flask import Flask, request
import requests
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/"

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
HR_EMAIL = os.getenv("HR_EMAIL")

user_states = {}

# Simulated interview schedule
INTERVIEW_SCHEDULE = {
    "101": {
        "job_title": "Staff Nurse",
        "date": "2025-04-28",
        "time": "10:00 AM",
        "location": "Nawaloka Hospital, Colombo",
        "interviewer": "Ms. Perera (HR Manager)"
    },
    "102": {
        "job_title": "HR Executive",
        "date": "2025-04-29",
        "time": "2:00 PM",
        "location": "Nawaloka HR Office, Negombo",
        "interviewer": "Mr. Fernando"
    },
    "103": {
        "job_title": "Pharmacist",
        "date": "2025-04-30",
        "time": "11:00 AM",
        "location": "Main Pharmacy, Colombo",
        "interviewer": "Dr. Silva"
    }
}

def send_email_with_attachment(subject, body, to_email, file_path, file_name):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = to_email
        msg.set_content(body)

        with open(file_path, "rb") as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Failed to send email:", e)
        return False

def handle_text(chat_id, user_id, user_name, message):
    message = message.lower()
    if user_id not in user_states:
        user_states[user_id] = {}

    if "job opening" in message or "vacancy" in message:
        user_states[user_id] = {"stage": "listing"}
        return (
            "📋 Current Job Openings:\n\n"
            "🔹 Job ID 101: Staff Nurse (Colombo)\n"
            "🔹 Job ID 102: HR Executive (Negombo)\n"
            "🔹 Job ID 103: Pharmacist (Colombo)\n\n"
            "Reply with 'apply for job id XXX' to upload your resume."
        )

    elif message.startswith("apply") and "id" in message:
        job_id = ''.join(filter(str.isdigit, message))
        user_states[user_id] = {"stage": "waiting_resume", "job_id": job_id}
        return f"👍 You've chosen Job ID {job_id}. Please upload your resume in PDF format."

    elif message in ["hi", "hello", "start"]:
        return (
            "👋 Welcome to the HR Recruitment Assistant Bot!\n\n"
            "You can ask me things like:\n"
            "- 'What are the job openings?'\n"
            "- 'Apply for Job ID 101'\n"
            "- Upload your resume (PDF)"
        )

    return "🤖 I'm your HR assistant. Ask me about job openings, applying, or uploading your resume."

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    user_id = data["message"]["from"]["id"]
    user_name = data["message"]["from"].get("first_name", "Candidate")

    if "document" in data["message"] and user_states.get(user_id, {}).get("stage") == "waiting_resume":
        file_id = data["message"]["document"]["file_id"]
        file_name = data["message"]["document"]["file_name"]
        job_id = user_states[user_id]["job_id"]

        if not file_name.lower().endswith(".pdf"):
            requests.post(TELEGRAM_API_URL, json={
                "chat_id": chat_id,
                "text": "⚠️ Please upload your resume in PDF format only."
            })
            return "ok"

        file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        file_url = f"{TELEGRAM_FILE_API}{file_path}"
        file_content = requests.get(file_url).content

        temp_path = f"/tmp/{file_name}"
        with open(temp_path, "wb") as f:
            f.write(file_content)

        subject = f"New Resume for Job ID {job_id}"
        body = f"Candidate {user_name} has applied for Job ID {job_id}. See attached resume."
        email_sent = send_email_with_attachment(subject, body, HR_EMAIL, temp_path, file_name)

        os.remove(temp_path)

        if email_sent:
            confirmation = "✅ Resume received and forwarded to HR."
        else:
            confirmation = "⚠️ Failed to send resume. Please try again later."

        requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": confirmation})

        if job_id in INTERVIEW_SCHEDULE:
            schedule = INTERVIEW_SCHEDULE[job_id]
            interview_msg = (
                f"📅 Interview Details:\n"
                f"Position: {schedule['job_title']}\n"
                f"Date: {schedule['date']} at {schedule['time']}\n"
                f"Location: {schedule['location']}\n"
                f"Contact: {schedule['interviewer']}"
            )
            requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": interview_msg})

        user_states[user_id]["stage"] = "done"

    else:
        message_text = data["message"].get("text", "")
        reply = handle_text(chat_id, user_id, user_name, message_text)
        requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": reply})

    return "ok"

@app.route("/")
def home():
    return "✅ Telegram HR Bot is running."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)