# A Telegram HR Recruitment Bot with Google Drive Upload and Fixed Secret Initialization

from flask import Flask, request
import requests
import os
import pandas as pd
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 🔐 Write service_account.json from Railway Secret IMMEDIATELY
if not os.path.exists("service_account.json") and os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON"):
    with open("service_account.json", "w") as f:
        creds_dict = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON"))
        json.dump(creds_dict, f)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/"

EXCEL_FILE = "Recruitment_Sample.xlsx"
INTERVIEW_FILE = "Interview_Schedule.xlsx"
user_states = {}

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def upload_to_drive(local_path, file_name):
    try:
        print("🔄 Starting upload to Google Drive...")

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        print("✅ Service account credentials loaded.")

        service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive service created.")

        file_metadata = {'name': file_name}
        media = MediaFileUpload(local_path, mimetype='application/pdf')

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        if not file_id:
            print("❌ File ID is missing after upload.")
            return None

        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        file_link = f"https://drive.google.com/file/d/{file_id}/view"
        print(f"✅ File uploaded successfully: {file_link}")
        return file_link

    except Exception as e:
        print("❌ Exception during upload_to_drive():", e)
        return None

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
                "- Upload your resume (PDF)\n"
                "- I’ll send your interview details if scheduled.")

    elif "interview" in message:
        job_id = user_states.get(user_id, {}).get("job_id")
        if job_id:
            return get_interview_details(job_id)
        else:
            return "❗ Please apply for a job first by mentioning the Job ID."

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

        temp_path = f"/tmp/temp_{file_name}"
        with open(temp_path, "wb") as f:
            f.write(file_content)

        file_link = upload_to_drive(temp_path, file_name)
        os.remove(temp_path)

        if not file_link:
            requests.post(TELEGRAM_API_URL, json={
                "chat_id": chat_id,
                "text": "⚠️ Upload failed. Please try again later or contact support."
            })
            return "ok"

        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": f"✅ Resume received and uploaded to Google Drive.\n📄 View here: {file_link}"
        })

        interview_details = get_interview_details(job_id)
        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": interview_details
        })
        user_states[user_id]["stage"] = "done"

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
    return "✅ Telegram HR Bot with Google Drive Secret Fix is running."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)