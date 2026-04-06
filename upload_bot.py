import os
import random
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ==============================
# إعدادات البوت
# ==============================
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
VIDEOS_FOLDER = "videos"

# ==============================
# قراءة token.json من GitHub Secrets
# يجب تعيين Secret باسم TOKEN_JSON
# ==============================
token_json_str = os.environ.get("TOKEN_JSON")
if not token_json_str:
    raise ValueError("TOKEN_JSON Secret not found! يجب إنشاءه على GitHub Secrets")

creds_data = json.loads(token_json_str)
creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

# تجديد صلاحية التوكن إذا انتهت
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

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
