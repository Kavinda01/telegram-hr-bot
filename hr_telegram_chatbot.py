# A Telegram HR Recruitment Bot with Resume Upload + Job Listing from Excel
# This bot helps with recruitment-related tasks and lists jobs + stores resumes

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

# Ensure folders exist
if not os.path.exists("resumes"):
    os.makedirs("resumes")

EXCEL_FILE = "Recruitment_Sample.xlsx"

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
def log_resume_submission(file_name, user_name, email="", job_id=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resume_df = pd.DataFrame([[timestamp, user_name, email, job_id, file_name]],
                             columns=["Timestamp", "Name", "Email", "Job ID Applied", "Notes"])
    if os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            existing = pd.read_excel(EXCEL_FILE, sheet_name="Resume Submissions")
            updated = pd.concat([existing, resume_df], ignore_index=True)
            updated.to_excel(writer, sheet_name="Resume Submissions", index=False)
    else:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            resume_df.to_excel(writer, sheet_name="Resume Submissions", index=False)

# Generate response for keyword queries
def get_response(message):
    message = message.lower()
    if "job opening" in message or "vacancy" in message:
        return load_open_jobs()
    elif "recruitment" in message or "hiring" in message:
        return ("I'm here to assist with recruitment! I can help with screening resumes, scheduling interviews, "
                "and answering frequently asked questions about roles and company policies. Let me know how you'd like to proceed.")
    elif "interview" in message:
        return ("To schedule or reschedule interviews, please provide the candidate's name, preferred date, and department.")
    elif "resume" in message or "cv" in message:
        return ("You can forward candidate resumes here. I’ll assist in organizing and tagging them based on job roles.")
    elif "candidate status" in message:
        return ("To check a candidate’s recruitment status, please provide their name or application ID.")
    else:
        return ("Hi! I'm your HR Recruitment Assistant bot. You can ask me about job openings, resumes, interviews, and more.")

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]

    if "document" in data["message"]:
        file_id = data["message"]["document"]["file_id"]
        file_name = data["message"]["document"]["file_name"]
        user_name = data["message"]["from"].get("first_name", "Anonymous")

        file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        file_url = f"{TELEGRAM_FILE_API}{file_path}"
        file_content = requests.get(file_url).content

        save_path = os.path.join("resumes", file_name)
        with open(save_path, "wb") as f:
            f.write(file_content)

        log_resume_submission(file_name, user_name)

        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": f"✅ Resume '{file_name}' received and saved successfully."
        })

    else:
        message_text = data["message"].get("text", "")
        reply = get_response(message_text)
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