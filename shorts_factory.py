"""
Professional Arabic Story Video Generator
Author: Advanced Video Processing System
Version: 2.0.0
"""

import re
import cv2
import numpy as np
import os
import random
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
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
    """Video configuration parameters"""
    # Dimensions
    img_width: int = 1080
    img_height: int = 1920
    
    # Video settings
    fps: int = 30
    scroll_speed: int = 100  # pixels per second
    
    # Text settings
    font_size: int = 110
    line_spacing: int = 50
    horizontal_margin: int = 90
    safe_zone_top: int = 160
    safe_zone_bottom: int = 250
    
    # Effect settings
    grain_intensity: float = 15.0
    flicker_range: Tuple[float, float] = (0.92, 1.08)
    vignette_intensity: float = 0.3
    
    # File paths
    backgrounds_folder: str = "backgrounds"
    font_path: str = "andalus.ttf"
    output_video_path: str = "story_video_smooth.mp4"
    music_folder: str = "music"
    stories_file: str = "stories.txt"
    videos_folder: str = "videos"  # New folder for videos
    
    @property
    def line_step(self) -> int:
        return self.font_size + self.line_spacing
    
    @property
    def max_text_width(self) -> int:
        return self.img_width - (self.horizontal_margin * 2)

class VideoGenerator:
    """Main video generator class with optimized performance"""
    
    def __init__(self, config: VideoConfig):
        self.config = config
        self._setup_paths()
        self._font_cache = {}
        
    def _setup_paths(self):
        """Create necessary directories if they don't exist"""
        Path(self.config.backgrounds_folder).mkdir(exist_ok=True)
        Path(self.config.music_folder).mkdir(exist_ok=True)
        Path(self.config.videos_folder).mkdir(exist_ok=True)  # Create videos folder
        
        # Update output path to be inside videos folder
        self.config.output_video_path = str(Path(self.config.videos_folder) / self.config.output_video_path)
        
    @lru_cache(maxsize=128)
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Cached font loading for better performance"""
        try:
            return ImageFont.truetype(self.config.font_path, size)
        except OSError:
            logger.warning(f"Font {self.config.font_path} not found, using default")
            return ImageFont.load_default()
    
    @staticmethod
    def fix_arabic(text: str) -> str:
        """Fix Arabic text rendering"""
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    
    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, 
                  max_width: int) -> List[str]:
        """Wrap text to fit within width constraints"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox(
                (0, 0), self.fix_arabic(test_line), font=font
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
        """Load random background image"""
        bg_path = Path(self.config.backgrounds_folder)
        
        if bg_path.exists() and any(bg_path.iterdir()):
            bg_files = [f for f in bg_path.glob('*') 
                       if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
            
            if bg_files:
                chosen = random.choice(bg_files)
                logger.info(f"Using background: {chosen.name}")
                img = Image.open(chosen).convert("RGB")
                return img.resize((self.config.img_width, self.config.img_height))
        
        logger.warning("No backgrounds found, using black background")
        return Image.new('RGB', (self.config.img_width, self.config.img_height), (0, 0, 0))
    
    def apply_effects(self, frame: Image.Image) -> Image.Image:
        """Apply visual effects for horror atmosphere"""
        img_np = np.array(frame).astype(np.float32)
        
        # Add grain effect
        if self.config.grain_intensity > 0:
            noise = np.random.normal(0, self.config.grain_intensity, img_np.shape)
            img_np += noise
        
        # Add flicker effect
        flicker = random.uniform(*self.config.flicker_range)
        img_np *= flicker
        
        # Add vignette effect
        if self.config.vignette_intensity > 0:
            h, w = img_np.shape[:2]
            X, Y = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
            vignette = 1 - self.config.vignette_intensity * (X**2 + Y**2)
            vignette = np.clip(vignette, 0.5, 1)
            img_np = img_np * vignette[:, :, np.newaxis]
        
        img_np = np.clip(img_np, 0, 255).astype(np.uint8)
        return Image.fromarray(img_np)
    
    def get_next_story(self) -> Optional[str]:
        """Get next story from file with proper error handling"""
        story_path = Path(self.config.stories_file)
        
        if not story_path.exists():
            logger.error(f"Story file not found: {self.config.stories_file}")
            return None
        
        try:
            with open(story_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            stories = [p.strip() for p in content.split("++") if p.strip()]
            
            if not stories:
                logger.warning("No stories left in file")
                return None
            
            selected = stories[0]
            remaining = stories[1:]
            
            # Update file with remaining stories
            with open(story_path, "w", encoding="utf-8") as f:
                if remaining:
                    f.write("\n\n++\n\n".join(remaining) + "\n\n++")
                else:
                    f.write("")
            
            logger.info(f"Selected story: {selected[:50]}...")
            return selected
            
        except Exception as e:
            logger.error(f"Error reading story file: {e}")
            return None
    
    def add_music(self, video_path: str) -> str:
        """Add random background music to video"""
        logger.info("Adding background music...")
        
        music_dir = Path(self.config.music_folder)
        if not music_dir.exists():
            logger.warning("Music folder not found")
            return video_path
        
        music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
        if not music_files:
            logger.warning("No music files found")
            return video_path
        
        selected = random.choice(music_files)
        logger.info(f"Selected music: {selected.name}")
        
        try:
            video = VideoFileClip(video_path)
            audio = AudioFileClip(str(selected))
            
            # Loop audio if shorter than video
            if audio.duration < video.duration:
                audio = audio.loop(duration=video.duration)
            
            final_audio = audio.subclip(0, video.duration).volumex(0.5)
            final_video = video.set_audio(final_audio)
            
            # Save final video in videos folder
            output_path = str(Path(self.config.videos_folder) / "final_output_with_music.mp4")
            final_video.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac",
                verbose=False,
                logger=None
            )
            
            video.close()
            audio.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding music: {e}")
            return video_path
    
    def create_video(self, text: str) -> str:
        """Create scrolling text video with effects"""
        logger.info("Starting video creation...")
        start_time = time.time()
        
        # Prepare text lines
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
        font = self._get_font(self.config.font_size)
        
        # Wrap text lines
        all_lines = []
        for sentence in sentences:
            wrapped = self.wrap_text(
                sentence, font, self.config.max_text_width
            )
            all_lines.extend([self.fix_arabic(line) for line in wrapped])
        
        if not all_lines:
            logger.error("No text lines to render")
            return ""
        
        logger.info(f"Rendering {len(all_lines)} lines of text")
        
        # Calculate video parameters
        start_y = self.config.img_height - self.config.safe_zone_bottom
        end_y = self.config.safe_zone_top - self.config.line_step
        total_distance = start_y - end_y + (len(all_lines) * self.config.line_step)
        total_duration = total_distance / self.config.scroll_speed
        total_frames = int(self.config.fps * total_duration)
        
        logger.info(f"Video duration: {total_duration:.2f} seconds")
        logger.info(f"Total frames: {total_frames}")
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(
            self.config.output_video_path,
            fourcc,
            self.config.fps,
            (self.config.img_width, self.config.img_height)
        )
        
        # Load background
        background = self.load_background()
        
        # Calculate line positions
        line_positions = [
            start_y + (i * self.config.line_step) 
            for i in range(len(all_lines))
        ]
        
        # Render frames
        scroll_per_frame = self.config.scroll_speed / self.config.fps
        
        for frame_num in range(total_frames):
            # Progress logging
            if frame_num % 30 == 0:
                progress = (frame_num / total_frames) * 100
                logger.info(f"Rendering progress: {progress:.1f}%")
            
            # Create frame
            frame = background.copy()
            draw = ImageDraw.Draw(frame)
            scroll_offset = scroll_per_frame * frame_num
            
            # Draw visible lines
            for i, (line_text, original_y) in enumerate(zip(all_lines, line_positions)):
                y_pos = original_y - scroll_offset
                
                # Skip if outside visible area
                if (y_pos < self.config.safe_zone_top - self.config.line_step or 
                    y_pos > self.config.img_height - self.config.safe_zone_bottom):
                    continue
                
                # Calculate text position
                bbox = draw.textbbox((0, 0), line_text, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (self.config.img_width - text_width) // 2
                
                # Draw text with outline
                draw.text((x_pos, y_pos), line_text, font=font,
                         fill="white", stroke_width=3, stroke_fill="black")
            
            # Apply effects
            frame = self.apply_effects(frame)
            
            # Convert to OpenCV format and write
            frame_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            video_writer.write(frame_cv)
        
        # Add hold frames at end
        hold_frames = self.config.fps * 2
        for _ in range(hold_frames):
            video_writer.write(frame_cv)
        
        video_writer.release()
        
        elapsed = time.time() - start_time
        logger.info(f"Video creation completed in {elapsed:.2f} seconds")
        
        return self.config.output_video_path
    
    def run(self) -> str:
        """Main execution pipeline"""
        logger.info("=" * 60)
        logger.info("Arabic Story Video Generator Started")
        logger.info("=" * 60)
        
        # Get story text
        story = self.get_next_story()
        if not story:
            logger.error("No story to process")
            return ""
        
        # Create video
        video_path = self.create_video(story)
        if not video_path:
            logger.error("Video creation failed")
            return ""
        
        # Add music
        final_path = self.add_music(video_path)
        
        logger.info("=" * 60)
        logger.info(f"✅ Success! Video saved to: {final_path}")
        logger.info("=" * 60)
        
        return final_path

# =============================
# MAIN EXECUTION
# =============================
def main():
    """Entry point with error handling"""
    try:
        # Initialize configuration
        config = VideoConfig()
        
        # Validate critical files
        if not Path(config.font_path).exists():
            logger.warning(f"Font file not found: {config.font_path}")
        
        # Create generator and run
        generator = VideoGenerator(config)
        result = generator.run()
        
        if result:
            logger.info(f"🎬 Video generated successfully: {result}")
        else:
            logger.error("❌ Video generation failed")
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Process interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
