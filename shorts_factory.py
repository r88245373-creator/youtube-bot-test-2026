"""
ULTIMATE Arabic Story Video Generator (TRUE Single Pass)
Video + Audio generated in one render using MoviePy
"""

import os
import time
import random
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, AudioFileClip

# Arabic support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def fix_ar(text):
        return get_display(arabic_reshaper.reshape(text))
except:
    def fix_ar(text): return text

# ================= CONFIG =================
WIDTH, HEIGHT = 1080, 1920
FPS = 30
FONT_PATH = "Andalus.ttf"
FONT_SIZE = 110

SCROLL_SPEED = 100
MARGIN_X = 90
SAFE_TOP = 160
SAFE_BOTTOM = 250

BG_FOLDER = "backgrounds"
MUSIC_FOLDER = "music"
OUTPUT = "videos"

Path(OUTPUT).mkdir(exist_ok=True)

# ================= HELPERS =================
def get_font():
    try:
        return ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except:
        return ImageFont.load_default()

def get_background():
    files = list(Path(BG_FOLDER).glob("*"))
    if files:
        img = Image.open(random.choice(files)).convert("RGB")
        return img.resize((WIDTH, HEIGHT))
    
    # fallback gradient
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        c = int(20 * (1 - y / HEIGHT))
        draw.line([(0, y), (WIDTH, y)], fill=(c, c, c+30))
    return img

def wrap_text(text, font):
    words = text.split()
    lines, current = [], []

    for w in words:
        test = " ".join(current + [w])
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0,0), fix_ar(test), font=font)
        width = bbox[2] - bbox[0]

        if width < (WIDTH - 2*MARGIN_X):
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]

    if current:
        lines.append(" ".join(current))

    return [fix_ar(l) for l in lines]

# ================= CORE =================
def create_video(story_text):

    font = get_font()
    bg = get_background()

    lines = []
    for s in story_text.split("\n"):
        lines += wrap_text(s, font)

    line_step = FONT_SIZE + 50

    start_y = HEIGHT - SAFE_BOTTOM
    end_y = SAFE_TOP - line_step

    total_distance = (start_y - end_y) + len(lines)*line_step
    duration = total_distance / SCROLL_SPEED

    print(f"Duration: {duration:.2f}s")

    def make_frame(t):
        img = bg.copy()
        draw = ImageDraw.Draw(img)

        offset = t * SCROLL_SPEED

        for i, line in enumerate(lines):
            y = start_y + i*line_step - offset

            if y < SAFE_TOP - line_step or y > HEIGHT - SAFE_BOTTOM:
                continue

            bbox = draw.textbbox((0,0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (WIDTH - w)//2

            draw.text(
                (x, y),
                fix_ar(line),  # ✅ نص عربي مضبوط RTL
                font=font,
                fill="white",
                stroke_width=3,
                stroke_fill="black"
            )

        frame = np.array(img)

        # effects
        noise = np.random.normal(0, 10, frame.shape)
        frame = np.clip(frame + noise, 0, 255)

        return frame.astype(np.uint8)

    video = VideoClip(make_frame, duration=duration)

    # ===== AUDIO =====
    music_files = list(Path(MUSIC_FOLDER).glob("*"))
    if music_files:
        music = AudioFileClip(str(random.choice(music_files)))

        if music.duration < duration:
            music = music.loop(duration=duration)

        music = music.subclip(0, duration).volumex(0.5)
        video = video.set_audio(music)

    output_path = f"{OUTPUT}/story_{int(time.time())}.mp4"

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac"
    )

    return output_path

def get_next_story(file_path="stories.txt"):
    if not os.path.exists(file_path):
        print("❌ الملف غير موجود")
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    separator = "++"
    index = content.find(separator)

    if index == -1:
        story = content.strip()
        open(file_path, "w", encoding="utf-8").close()
        return story if story else None

    story = content[:index].strip()
    remaining = content[index + len(separator):].strip()

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(remaining)

    return story

# ================= RUN =================
if __name__ == "__main__":

    story = get_next_story()  # ✅ جلب أول قصة

    if story:
        path = create_video(story)
        print("✅ DONE:", path)
    else:
        print("❌ لا توجد قصص")
