# A Telegram HR Recruitment Bot with Full Flow: Job Listings → Job Selection → Resume → Interview Details
# This bot manages recruitment from job listings to interview scheduling using Excel for data storage

from flask import Flask, request
import requests
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# Bot token from environment variable or hardcoded (replace with your token)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/"

# File paths
EXCEL_FILE = "Recruitment_Sample.xlsx"
INTERVIEW_FILE = "Interview_Schedule.xlsx"

# State tracker
user_states = {}

# Ensure folders exist
if not os.path.exists("resumes"):
    os.makedirs("resumes")

# Load job openings from Excel
def load_open_jobs():
    if not os.path.exists(EXCEL_FILE):
        return "⚠️ Job openings data not found."
    df = pd.read_excel(EXCEL_FILE, sheet_name="Job Openings")
    df_open = df[df["Status"].str.lower() == "open"]
    if df_open.empty:
        return "📋 There are currently no open job positions."

    message = "📋 Current Job Openings:\n\n"
    for _, row in df_open.iterrows():
        message += (
            f"🔹 {row['Job Title']} (ID: {row['Job ID']})\n"
            f"   Department: {row['Department']}\n"
            f"   Location: {row['Location']}\n"
            f"   Openings: {row['Openings']}\n"
            f"   Contact: {row['Contact Email']}\n\n"
        )
    return message

# Save resume entry in Excel
def log_resume_submission(file_name, user_name, job_id):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resume_df = pd.DataFrame([[timestamp, user_name, job_id, file_name]],
                             columns=["Timestamp", "Name", "Job ID Applied", "Notes"])
    if os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            existing = pd.read_excel(EXCEL_FILE, sheet_name="Resume Submissions")
            updated = pd.concat([existing, resume_df], ignore_index=True)
            updated.to_excel(writer, sheet_name="Resume Submissions", index=False)
    else:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            resume_df.to_excel(writer, sheet_name="Resume Submissions", index=False)

# Load interview schedule
def get_interview_details(job_id):
    if not os.path.exists(INTERVIEW_FILE):
        return "📅 Interview schedule not available."
    df = pd.read_excel(INTERVIEW_FILE)
    interview = df[df["Job ID"] == job_id]
    if interview.empty:
        return "📅 No interview schedule found for this job ID."
    row = interview.iloc[0]
    return (f"📆 Your interview for {row['Job Title']} is scheduled on {row['Date']} at {row['Time']}\n"
            f"Location: {row['Location']}\nContact: {row['Interviewer']}")

# Handle messages and states
def handle_text(chat_id, user_id, user_name, message):
    message = message.lower()
    if user_id not in user_states:
        user_states[user_id] = {}

    if "job opening" in message or "vacancy" in message:
        user_states[user_id] = {"stage": "listing"}
        return load_open_jobs()

    elif message.startswith("apply") and "id" in message:
        job_id = ''.join(filter(str.isdigit, message))
        user_states[user_id] = {"stage": "waiting_resume", "job_id": int(job_id)}
        return f"👍 Noted your interest in Job ID {job_id}. Please upload your resume in PDF format."

    elif message in ["hi", "hello", "start"]:
        return ("👋 Welcome to the HR Recruitment Assistant Bot!\n\n"
                "You can ask me things like:\n"
                "- 'What are the job openings?'\n"
                "- 'Apply for Job ID 101'\n"
                "- Then upload your resume\n"
                "- I'll then share your interview details if scheduled.")

    elif "interview" in message:
        job_id = user_states.get(user_id, {}).get("job_id")
        if job_id:
            return get_interview_details(job_id)
        else:
            return "❗ Please apply for a job first by mentioning the Job ID."

    elif "contact hr" in message:
        return "📞 You can reach our HR team at hr@nawaloka.com or call extension 204."

    return "🤖 I'm your HR assistant. Ask me about job openings, applying, uploading your resume, or interview details."

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

        file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        file_url = f"{TELEGRAM_FILE_API}{file_path}"
        file_content = requests.get(file_url).content

        save_path = os.path.join("resumes", file_name)
        with open(save_path, "wb") as f:
            f.write(file_content)

        log_resume_submission(file_name, user_name, job_id)
        user_states[user_id]["stage"] = "done"

        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": f"✅ Resume received for Job ID {job_id}. Let me send you your interview details next..."
        })

        interview_details = get_interview_details(job_id)
        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": interview_details
        })

    else:
        message_text = data["message"].get("text", "")
        reply = handle_text(chat_id, user_id, user_name, message_text)
        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": reply
        })

    return "ok"

@app.route("/")
def home():
    return "✅ Telegram HR Recruitment Bot is running."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)