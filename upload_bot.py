import os
import random
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# ==============================
# إعدادات البوت
# ==============================
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
VIDEOS_FOLDER = "videos"

def get_authenticated_service():
    token_json_str = os.environ.get("YOUTUBE_TOKEN_JSON")
    if not token_json_str:
        raise ValueError("❌ خطأ: YOUTUBE_TOKEN_JSON غير موجود في GitHub Secrets!")

    creds_data = json.loads(token_json_str)
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # التحقق من صلاحية التوكن وتجديده آلياً
    if creds and creds.expired and creds.refresh_token:
        print("🔄 التوكن منتهي الصلاحية، يتم التجديد الآن...")
        creds.refresh(Request())
        # ملاحظة: في GitHub Actions، التوكن المتجدد لن يحفظ تلقائياً في السيكريتس
        # لكنه سيعمل خلال جلسة التشغيل الحالية.
    
    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, file_path):
    try:
        file_name = os.path.basename(file_path)
        x = random.randint(1000, 9999)
        title = f"قصص من المصفوفة السرية ♾️ #Shorts {x}"

        print(f"🚀 جاري رفع: {file_name}...")

        request_body = {
            "snippet": {
                "title": title,
                "description": "#shorts #mystery #test",
                "tags": ["shorts", "mystery"],
                "categoryId": "24",
                "defaultLanguage": "ar",
                "defaultAudioLanguage": "ar"
            },
            "status": {
                "privacyStatus": "public",  # يمكنك تغييرها لـ private للتجربة
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            file_path, 
            mimetype="video/*", 
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        # نظام الرفع مع إظهار التقدم (اختياري)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"📦 تم رفع {int(status.progress() * 100)}%...")

        print(f"✅ تم الرفع بنجاح! ID الفيديو: {response['id']}")
        
        # حذف الملف بعد التأكد من الرفع
        os.remove(file_path)
        print(f"🗑️ تم حذف الملف المحلي: {file_name}")

    except HttpError as e:
        print(f"❌ حدث خطأ في اليوتيوب API: {e}")
    except Exception as e:
        print(f"⚠️ حدث خطأ غير متوقع: {e}")

if __name__ == "__main__":
    # التأكد من وجود المجلد
    if not os.path.exists(VIDEOS_FOLDER):
        print(f"📁 المجلد '{VIDEOS_FOLDER}' غير موجود، يتم إنشاؤه الآن...")
        os.makedirs(VIDEOS_FOLDER)

    youtube_service = get_authenticated_service()
    
    video_files = [f for f in os.listdir(VIDEOS_FOLDER) if f.endswith((".mp4", ".mov", ".mkv"))]
    
    if not video_files:
        print("ℹ️ لا توجد فيديوهات للرفع في المجلد.")
    else:
        for video_file in video_files:
            upload_video(youtube_service, os.path.join(VIDEOS_FOLDER, video_file))
