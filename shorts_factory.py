"""
Professional Arabic Story Video Generator
Author: Advanced Video Processing System
Version: 2.1.0 - Fixed Arabic Rendering Logic
"""

import re
import cv2
import numpy as np
import os
import random
import logging
import time
import warnings
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Import with error handling
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError as e:
    print(f"Warning: Arabic text libraries not available: {e}")
    def arabic_reshaper_placeholder(text): return text
    def get_display_placeholder(text): return text
    arabic_reshaper = type('obj', (object,), {'reshape': arabic_reshaper_placeholder})
    get_display = get_display_placeholder

from moviepy.editor import VideoFileClip, AudioFileClip

# =============================
# LOGGING CONFIGURATION
# =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================
# CONFIGURATION CLASS
# =============================
@dataclass
class VideoConfig:
    img_width: int = 1080
    img_height: int = 1920
    fps: int = 30
    scroll_speed: int = 100 
    font_size: int = 110
    line_spacing: int = 50
    horizontal_margin: int = 90
    safe_zone_top: int = 160
    safe_zone_bottom: int = 250
    grain_intensity: float = 15.0
    flicker_range: Tuple[float, float] = (0.92, 1.08)
    vignette_intensity: float = 0.3
    backgrounds_folder: str = "backgrounds"
    font_path: str = "Andalus.ttf"
    output_video_path: str = "story_video_smooth.mp4"
    music_folder: str = "music"
    stories_file: str = "stories.txt"
    videos_folder: str = "videos"
    
    @property
    def line_step(self) -> int:
        return self.font_size + self.line_spacing
    
    @property
    def max_text_width(self) -> int:
        return self.img_width - (self.horizontal_margin * 2)

class VideoGenerator:
    def __init__(self, config: VideoConfig):
        self.config = config
        self._setup_paths()
        self._font_cache = {}
        
    def _setup_paths(self):
        Path(self.config.backgrounds_folder).mkdir(exist_ok=True)
        Path(self.config.music_folder).mkdir(exist_ok=True)
        Path(self.config.videos_folder).mkdir(exist_ok=True)
        self.config.output_video_path = str(Path(self.config.videos_folder) / Path(self.config.output_video_path).name)
        
    @lru_cache(maxsize=128)
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.config.font_path, size)
    
    @staticmethod
    def fix_arabic(text: str) -> str:
        """Fix Arabic text rendering with enhanced reshaping logic"""
        try:
            # Reshaping is crucial for joining letters correctly
            reshaped_text = arabic_reshaper.reshape(text)
            # bidi algorithm is crucial for correct character order (RTL)
            return get_display(reshaped_text)
        except Exception:
            return text
    
    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text with correct Arabic width calculation"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            # We MUST fix the Arabic before calculating the bounding box
            fixed_test_line = self.fix_arabic(test_line)
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox(
                (0, 0), fixed_test_line, font=font
            )
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
    
    def load_background(self) -> Image.Image:
        bg_path = Path(self.config.backgrounds_folder)
        if bg_path.exists() and any(bg_path.iterdir()):
            bg_files = [f for f in bg_path.glob('*') if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
            if bg_files:
                chosen = random.choice(bg_files)
                img = Image.open(chosen).convert("RGB")
                return img.resize((self.config.img_width, self.config.img_height))
        return Image.new('RGB', (self.config.img_width, self.config.img_height), (0, 0, 0))
    
    def apply_effects(self, frame: Image.Image) -> Image.Image:
        img_np = np.array(frame).astype(np.float32)
        if self.config.grain_intensity > 0:
            noise = np.random.normal(0, self.config.grain_intensity, img_np.shape)
            img_np += noise
        flicker = random.uniform(*self.config.flicker_range)
        img_np *= flicker
        if self.config.vignette_intensity > 0:
            h, w = img_np.shape[:2]
            X, Y = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
            vignette = 1 - self.config.vignette_intensity * (X**2 + Y**2)
            vignette = np.clip(vignette, 0.5, 1)
            img_np = img_np * vignette[:, :, np.newaxis]
        img_np = np.clip(img_np, 0, 255).astype(np.uint8)
        return Image.fromarray(img_np)
    
    def get_next_story(self) -> Optional[str]:
        story_path = Path(self.config.stories_file)
        if not story_path.exists(): return None
        try:
            with open(story_path, "r", encoding="utf-8") as f:
                content = f.read()
            stories = [p.strip() for p in content.split("++") if p.strip()]
            if not stories: return None
            selected = stories[0]
            remaining = stories[1:]
            with open(story_path, "w", encoding="utf-8") as f:
                if remaining: f.write("\n\n++\n\n".join(remaining) + "\n\n++")
                else: f.write("")
            return selected
        except Exception: return None
    
    def add_music(self, video_path: str) -> str:
        music_dir = Path(self.config.music_folder)
        music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
        if not music_files: return video_path
        selected = random.choice(music_files)
        try:
            video = VideoFileClip(video_path)
            audio = AudioFileClip(str(selected))
            if audio.duration < video.duration:
                audio = audio.loop(duration=video.duration)
            final_audio = audio.subclip(0, video.duration).volumex(0.5)
            final_video = video.set_audio(final_audio)
            output_path = str(Path(self.config.videos_folder) / "final_output_with_music.mp4")
            final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
            video.close()
            audio.close()
            return output_path
        except Exception: return video_path
    
    def create_video(self, text: str) -> str:
        logger.info("Starting video creation...")
        start_time = time.time()
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
        font = self._get_font(self.config.font_size)
        
        all_lines = []
        for sentence in sentences:
            wrapped = self.wrap_text(sentence, font, self.config.max_text_width)
            # Store the final fixed Arabic line for rendering
            all_lines.extend([self.fix_arabic(line) for line in wrapped])
        
        if not all_lines: return ""
        
        start_y = self.config.img_height - self.config.safe_zone_bottom
        end_y = self.config.safe_zone_top - self.config.line_step
        total_distance = start_y - end_y + (len(all_lines) * self.config.line_step)
        total_duration = total_distance / self.config.scroll_speed
        total_frames = int(self.config.fps * total_duration)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(self.config.output_video_path, fourcc, self.config.fps, (self.config.img_width, self.config.img_height))
        background = self.load_background()
        line_positions = [start_y + (i * self.config.line_step) for i in range(len(all_lines))]
        scroll_per_frame = self.config.scroll_speed / self.config.fps
        
        for frame_num in range(total_frames):
            frame = background.copy()
            draw = ImageDraw.Draw(frame)
            scroll_offset = scroll_per_frame * frame_num
            
            for line_text, original_y in zip(all_lines, line_positions):
                y_pos = original_y - scroll_offset
                if (y_pos < self.config.safe_zone_top - self.config.line_step or y_pos > self.config.img_height - self.config.safe_zone_bottom):
                    continue
                
                bbox = draw.textbbox((0, 0), line_text, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (self.config.img_width - text_width) // 2
                draw.text((x_pos, y_pos), line_text, font=font, fill="white", stroke_width=3, stroke_fill="black")
            
            frame = self.apply_effects(frame)
            frame_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            video_writer.write(frame_cv)
        
        video_writer.release()
        return self.config.output_video_path
    
    def run(self) -> str:
        story = self.get_next_story()
        if not story: return ""
        video_path = self.create_video(story)
        if not video_path: return ""
        return self.add_music(video_path)

def main():
    try:
        config = VideoConfig()
        if not Path(config.font_path).exists():
            logger.error(f"CRITICAL ERROR: Font file not found at {config.font_path}.")
            return
        generator = VideoGenerator(config)
        result = generator.run()
        if result: logger.info(f"✅ Success: {result}")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
