"""
Professional Arabic Story Video Generator - GITHUB ACTIONS OPTIMIZED
Version: 2.5.0 - Ultimate Arabic Fix
"""

import re
import cv2
import numpy as np
import os
import random
import logging
import warnings
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Robust Arabic Library Import
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False

from moviepy.editor import VideoFileClip, AudioFileClip

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VideoConfig:
    img_width: int = 1080
    img_height: int = 1920
    fps: int = 30
    scroll_speed: int = 110 
    font_size: int = 105
    line_spacing: int = 55
    horizontal_margin: int = 100
    safe_zone_top: int = 200
    safe_zone_bottom: int = 300
    grain_intensity: float = 12.0
    flicker_range: Tuple[float, float] = (0.95, 1.05)
    vignette_intensity: float = 0.4
    backgrounds_folder: str = "backgrounds"
    font_path: str = "Andalus.ttf" 
    output_video_path: str = "story_video_smooth.mp4"
    music_folder: str = "music"
    stories_file: str = "stories.txt"
    videos_folder: str = "videos"
    
    @property
    def max_text_width(self) -> int:
        return self.img_width - (self.horizontal_margin * 2)

class VideoGenerator:
    def __init__(self, config: VideoConfig):
        self.config = config
        self._setup_paths()
        # إعداد محرك معالجة النصوص العربية مرة واحدة لتحسين الأداء
        self.reshaper_config = {
            'delete_harakat': False,
            'support_ligatures': True,
            'ARABIC_LIGATURES': True
        }
        self.reshaper = arabic_reshaper.ArabicReshaper(configuration=self.reshaper_config)

    def _setup_paths(self):
        for folder in [self.config.backgrounds_folder, self.config.music_folder, self.config.videos_folder]:
            Path(folder).mkdir(exist_ok=True)
        self.config.output_video_path = str(Path(self.config.videos_folder) / Path(self.config.output_video_path).name)

    @lru_cache(maxsize=32)
    def _get_font(self, size: int):
        try:
            return ImageFont.truetype(self.config.font_path, size)
        except Exception:
            logger.error(f"Could not load font {self.config.font_path}, using default.")
            return ImageFont.load_default()

    def fix_arabic_logic(self, text: str) -> str:
        """المعالج الاحترافي لربط الحروف العربية وتصحيح الاتجاه"""
        if not text.strip() or not ARABIC_SUPPORT:
            return text
        # 1. ربط الحروف (Reshaping)
        reshaped = self.reshaper.reshape(text)
        # 2. تصحيح الاتجاه (Bidi)
        return get_display(reshaped)

    def wrap_text_arabic(self, text: str, font, max_width: int) -> List[str]:
        """تقسيم النص لأسطر مع مراعاة خصائص اللغة العربية"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            # يجب إصلاح النص قبل قياس عرضه لأن الربط يغير الحجم
            fixed_test = self.fix_arabic_logic(test_line)
            
            bbox = font.getbbox(fixed_test)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        return lines

    def apply_visual_effects(self, frame_np: np.ndarray) -> np.ndarray:
        """إضافة Grain و Flicker و Vignette لجمالية الفيديو"""
        h, w = frame_np.shape[:2]
        # Grain
        noise = np.random.normal(0, self.config.grain_intensity, frame_np.shape).astype(np.float32)
        frame_np = frame_np.astype(np.float32) + noise
        # Flicker
        frame_np *= random.uniform(*self.config.flicker_range)
        # Vignette
        X, Y = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
        vignette = 1 - self.config.vignette_intensity * (X**2 + Y**2)
        frame_np *= np.clip(vignette[:, :, np.newaxis], 0.4, 1)
        
        return np.clip(frame_np, 0, 255).astype(np.uint8)

    def add_music(self, video_path: str) -> str:
        music_files = list(Path(self.config.music_folder).glob("*.mp3"))
        if not music_files:
            return video_path
        
        try:
            logger.info(f"Adding audio from: {random.choice(music_files).name}")
            video = VideoFileClip(video_path)
            audio = AudioFileClip(str(random.choice(music_files)))
            
            if audio.duration < video.duration:
                audio = audio.loop(duration=video.duration)
            
            final_audio = audio.subclip(0, video.duration).volumex(0.4)
            final_video = video.set_audio(final_audio)
            
            output_path = str(Path(self.config.videos_folder) / "final_output_with_music.mp4")
            final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=self.config.fps, logger=None)
            return output_path
        except Exception as e:
            logger.error(f"Music Error: {e}")
            return video_path

    def create_video(self, story_text: str) -> str:
        font = self._get_font(self.config.font_size)
        raw_lines = []
        for p in story_text.split('\n'):
            if p.strip():
                raw_lines.extend(self.wrap_text_arabic(p, font, self.config.max_text_width))
        
        # تحويل الأسطر لشكلها النهائي المربوط
        processed_lines = [self.fix_arabic_logic(line) for line in raw_lines]
        
        line_step = self.config.font_size + self.config.line_spacing
        total_height = len(processed_lines) * line_step
        duration = (total_height + self.config.img_height) / self.config.scroll_speed
        total_frames = int(duration * self.config.fps)

        # تجهيز الفيديو
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.config.output_video_path, fourcc, self.config.fps, (self.config.img_width, self.config.img_height))
        
        # تحميل الخلفية
        bg = Image.new('RGB', (self.config.img_width, self.config.img_height), (15, 15, 15))
        bg_folder = Path(self.config.backgrounds_folder)
        bg_files = list(bg_folder.glob("*.jpg")) + list(bg_folder.glob("*.png"))
        if bg_files:
            bg = Image.open(random.choice(bg_files)).convert("RGB").resize((self.config.img_width, self.config.img_height))

        logger.info(f"Generating {total_frames} frames...")
        
        for f in range(total_frames):
            frame = bg.copy()
            draw = ImageDraw.Draw(frame)
            y_offset = self.config.img_height - (f * (self.config.scroll_speed / self.config.fps))
            
            for i, line in enumerate(processed_lines):
                current_y = y_offset + (i * line_step)
                if -100 < current_y < self.config.img_height + 100:
                    bbox = font.getbbox(line)
                    x_pos = (self.config.img_width - (bbox[2] - bbox[0])) // 2
                    # رسم ظل خفيف للنص لزيادة الوضوح
                    draw.text((x_pos+2, current_y+2), line, font=font, fill=(0,0,0,180))
                    draw.text((x_pos, current_y), line, font=font, fill="white")

            # تحويل لـ OpenCV وتطبيق المؤثرات
            frame_np = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            frame_np = self.apply_visual_effects(frame_np)
            out.write(frame_np)

        out.release()
        return self.config.output_video_path

    def run(self):
        story_path = Path(self.config.stories_file)
        if not story_path.exists():
            logger.error("Stories file missing!")
            return
            
        with open(story_path, 'r', encoding='utf-8') as f:
            content = f.read().split('++')
        
        stories = [s.strip() for s in content if s.strip()]
        if not stories:
            logger.info("No stories to process.")
            return

        selected_story = stories[0]
        video_file = self.create_video(selected_story)
        final_file = self.add_music(video_file)
        
        # تحديث ملف القصص (حذف التي تم معالجتها)
        with open(story_path, 'w', encoding='utf-8') as f:
            f.write('\n\n++\n\n'.join(stories[1:]))
            if len(stories) > 1: f.write('\n\n++')
            
        logger.info(f"Successfully created: {final_file}")

if __name__ == "__main__":
    gen = VideoGenerator(VideoConfig())
    gen.run()
