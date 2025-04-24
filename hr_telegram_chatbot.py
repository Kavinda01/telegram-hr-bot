# A Telegram HR Recruitment Bot with Excel + Mistral AI via OpenRouter

from flask import Flask, request
import requests
import os
import json
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/"

GDRIVE_SECRET = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ['https://www.googleapis.com/auth/drive.file']

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

JOB_OPENINGS_FILE = "Recruitment_Job_Openings.xlsx"
INTERVIEW_SCHEDULE_FILE = "Interview_Schedule.xlsx"

user_states = {}

def upload_to_drive(local_path, file_name):
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            with open(SERVICE_ACCOUNT_FILE, "w") as f:
                f.write(GDRIVE_SECRET)

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': file_name,
            'parents': [GDRIVE_FOLDER_ID] if GDRIVE_FOLDER_ID else []
        }
        media = MediaFileUpload(local_path, mimetype='application/pdf')
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception as e:
        print("Drive upload failed:", e)
        return None

def get_open_jobs():
    if not os.path.exists(JOB_OPENINGS_FILE):
        return "⚠️ Job openings file not found."
    df = pd.read_excel(JOB_OPENINGS_FILE, sheet_name="Job Openings")
    df_open = df[df["Status"].str.lower() == "open"]
    if df_open.empty:
        return "📋 There are currently no open job positions."
    msg = "📋 Current Job Openings:\n\n"
    for _, row in df_open.iterrows():
        msg += (f"🔹 {row['Job Title']} (ID: {row['Job ID']})\n"
                f"   Department: {row['Department']}\n"
                f"   Location: {row['Location']}\n"
                f"   Openings: {row['Openings']}\n"
                f"   Contact: {row['Contact Email']}\n\n")
    return msg

def get_interview_details(job_id):
    if not os.path.exists(INTERVIEW_SCHEDULE_FILE):
        return "📅 Interview schedule file not found."
    df = pd.read_excel(INTERVIEW_SCHEDULE_FILE, sheet_name="Schedule")
    interview = df[df["Job ID"] == int(job_id)]
    if interview.empty:
        return "📅 No interview schedule found for this job ID."
    row = interview.iloc[0]
    return (f"📅 Interview Details:\n"
            f"Position: {row['Job Title']}\n"
            f"Date: {row['Date'].strftime('%Y-%m-%d')} at {row['Time']}\n"
            f"Location: {row['Location']}\n"
            f"Contact: {row['Interviewer']}")

def ask_openrouter(question):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "system", "content": "You are a helpful HR assistant for a hospital."},
                {"role": "user", "content": question}
            ]
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"].strip()
        else:
            print("Unexpected OpenRouter response:", result)
            return "🤖 Sorry, I couldn’t get a proper answer right now. Please try again later."
    except Exception as e:
        print("OpenRouter API error:", e)
        return "🤖 I'm temporarily unable to answer that. Please try again later."

def handle_text(chat_id, user_id, user_name, message):
    message_lower = message.lower()
    if user_id not in user_states:
        user_states[user_id] = {}

    if "job opening" in message_lower or "vacancy" in message_lower:
        user_states[user_id] = {"stage": "listing"}
        return get_open_jobs()

    elif message_lower.startswith("apply") and "id" in message_lower:
        job_id = ''.join(filter(str.isdigit, message_lower))
        user_states[user_id] = {"stage": "waiting_resume", "job_id": job_id}
        return f"👍 You've chosen Job ID {job_id}. Please upload your resume in PDF format."

    elif message_lower in ["hi", "hello", "start"]:
        return (
            "👋 Welcome to the HR Recruitment Assistant Bot!\n\n"
            "You can ask me things like:\n"
            "- 'What are the job openings?'\n"
            "- 'Apply for Job ID 101'\n"
            "- Upload your resume (PDF)\n"
            "- Ask HR-related questions"
        )

    else:
        return ask_openrouter(message)

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

        file_link = upload_to_drive(temp_path, file_name)
        os.remove(temp_path)

        if file_link:
            confirmation = f"✅ Resume uploaded successfully.\n📄 View: {file_link}"
        else:
            confirmation = "⚠️ Failed to upload resume. Please try again later."

        requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": confirmation})

        interview_msg = get_interview_details(job_id)
        requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": interview_msg})

        user_states[user_id]["stage"] = "done"

    else:
        message_text = data["message"].get("text", "")
        reply = handle_text(chat_id, user_id, user_name, message_text)
        requests.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": reply})

    return "ok"

@app.route("/")
def home():
    return "✅ Telegram HR Bot with Excel + OpenRouter AI (Mistral) is running."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)