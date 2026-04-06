import os
import random
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
import json

# ==============================
# إعدادات البوت
# ==============================
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
VIDEOS_FOLDER = "videos"
TOKEN_FILE = "token.json"

# ==============================
# قراءة بيانات العميل من البيئة (GitHub Secrets)
# يجب تعيين GitHub Secrets: CLIENT_ID و CLIENT_SECRET
# ==============================
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob","http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

# ==============================
# تحميل أو إنشاء بيانات الاعتماد
# ==============================
creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
        creds = flow.run_console()
    # حفظ token.json
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

# ==============================
# رفع فيديو وحذفه بعد الرفع
# ==============================
def upload_video(file_path):
    x = random.randint(100, 1000)
    title = f"قصص من المصفوفة السرية ♾️ - القصة {x}"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "test",
                "tags": ["test"],
                "categoryId": "24",  # Entertainment
                "defaultLanguage": "ar",
                "defaultAudioLanguage": "ar",
                "recordingDetails": {"locationDescription": "Morocco"}
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "madeForKids": False,
                "embeddable": True,
                "license": "youtube"
            }
        },
        media_body=MediaFileUpload(file_path)
    )
    response = request.execute()
    print(f"تم رفع الفيديو: {response['id']}")

    # حذف الفيديو بعد رفعه
    os.remove(file_path)
    print(f"تم حذف الفيديو المحلي: {file_path}")

# رفع كل الفيديوهات الموجودة في المجلد
for video_file in os.listdir(VIDEOS_FOLDER):
    if video_file.endswith((".mp4", ".mov", ".mkv")):
        upload_video(os.path.join(VIDEOS_FOLDER, video_file))
