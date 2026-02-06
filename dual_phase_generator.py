# -*- coding: utf-8 -*-
"""
Dual-Phase Viral Video Automation Script
Generates: (A) Digital Human Phase + (B) Movie Clip Phase
Output can be concatenated with additional End Card Phase later
"""

__version__ = "1.0.0"

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS & SETUP
# ═══════════════════════════════════════════════════════════════════════════

import os
import sys
import glob
import random
import math
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Union

import numpy as np
from PIL import Image, ImageFilter, ImageOps
import PIL.Image

# Ensure ANTIALIAS compatibility
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips, vfx
)

# Import proglog for custom MoviePy progress logging
try:
    from proglog import ProgressBarLogger
    PROGLOG_AVAILABLE = True
except ImportError:
    PROGLOG_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VideoConfig:
    """
    Centralized configuration for video generation.
    Controls all visual parameters, layout logic, and randomization ranges.
    """
    # ─── RESOLUTION ───
    width: int = 1080
    height: int = 1920
    
    # ─── AUDIO ───
    bgm_volume: float = 0.32  # Headless Param: Normalized audio level
    
    # ─── DIGITAL HUMAN ───
    digital_human_size: float = 1.0  # Scale factor
    
    # ─── IMAGE PROCESSING ───
    stroke_width: int = 5      # Pixels for white outline
    chroma_key_threshold: int = 140  # Green screen sensitivity (0-255)
    
    # ─── ANIMATION & MOTION (HEADLESS PARAMS) ───
    bg_scroll_speed: int = 950       # Headless Param: Pixels per second
    gap_between_images: int = 20     # Gap between posters in infinite scroll
    
    # Floating Panel Animation (Sin Wave)
    floating_panel_amplitude: int = 8  # Pixels
    floating_panel_period: float = 3.0 # Seconds
    
    # Ad Text Pulse
    adtext_pulse_scale: float = 0.05      # 5% size variation (Headless Param)
    adtext_pulse_frequency: float = 1.5   # Hz (Headless Param)
    
    # Finger Tap Animation
    finger_tap_amplitude: int = 12        # Pixels
    finger_tap_frequency: float = 8.0     # Hz (speed of tap)
    
    # ─── LAYOUT & SAFE ZONES (HEADLESS PARAMS) ───
    safe_zone_margin: int = 50       # Edge padding
    searchbox_phase_b_y: int = 250   # Y-coordinate for Searchbox in Phase B
    finger_target_height: int = 250  # Normalized height for finger cursor
    
    # Floating Panels
    floating_panel_margin: int = 20
    floating_panel_jitter: int = 10  # Headless Param: Random Y-offset range (+/- px) to prevent burning
    avatar_safe_zone: int = 550      # Headless Param: Reserved height at bottom for avatar (pixels from bottom)
    
    # Component Dimensions
    # Searchbox
    searchbox_padding: int = 20      # Headless Param: Total width reduction (VideoWidth - Padding)
    searchbox_y_offset: int = 5      # Gap between elements
    searchbox_opacity_min: float = 0.95 # Headless Param
    searchbox_opacity_max: float = 1.0  # Headless Param
    
    # HD Icon
    hd_icon_height: int = 60
    hd_icon_padding: int = 20
    hd_icon_opacity: float = 0.85
    
    # Overlays
    overlay_width_ratio: float = 0.4  # occupy 40% of screen width
    overlay_opacity_min: float = 0.65
    overlay_opacity_max: float = 0.75
    overlay_gap_min: float = 2.0      # Headless Param: Seconds between overlays
    overlay_gap_max: float = 3.0      # Headless Param: Seconds between overlays
    
    # ─── ASSETS ───
    validation_required: List[str] = field(default_factory=lambda: ['avatars', 'movies', 'backgrounds'])

# Initialize Logger
def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger("DualPhaseGen")

# ═══════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

class StreamlitLogger(ProgressBarLogger if PROGLOG_AVAILABLE else object):
    """
    Custom logger that bridges MoviePy's proglog to Streamlit's progress bar.
    Provides real-time rendering progress updates.
    """
    
    def __init__(self, st_progress_bar: Any = None, st_status_text: Any = None):
        if PROGLOG_AVAILABLE:
            super().__init__()
        self.st_progress_bar = st_progress_bar
        self.st_status_text = st_status_text
        self.last_percent = 0
    
    def bars_callback(self, bar: str, attr: str, value: Any, old_value: Any = None) -> None:
        if bar == 't' and attr == 'index':
            # Get total frames if available
            total = self.bars.get(bar, {}).get('total', None)
            
            if total and total > 0:
                percent = min(value / total, 1.0)
                
                # Only update if progress changed significantly (avoid flickering)
                if percent - self.last_percent >= 0.01 or percent >= 1.0:
                    self.last_percent = percent
                    
                    if self.st_progress_bar:
                        try:
                            self.st_progress_bar.progress(percent, text=f"Rendering: {int(percent * 100)}%")
                        except:
                            pass
                    
                    if self.st_status_text:
                        try:
                            self.st_status_text.text(f"Frame {value}/{total} ({int(percent * 100)}%)")
                        except:
                            pass

class ImageProcessor:
    """Advanced image processing for effects"""
    
    @staticmethod
    def create_white_stroke(frame: np.ndarray, stroke_width: int = 5) -> np.ndarray:
        """Apply white stroke/glow to non-transparent pixels"""
        img = Image.fromarray(frame.astype('uint8'))
        
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        alpha = img.split()[3]
        
        # Create dilated mask for stroke
        dilated = alpha.copy()
        for _ in range(stroke_width):
            dilated = dilated.filter(ImageFilter.MaxFilter(3))
        
        stroke_img = Image.new('RGBA', img.size, (255, 255, 255, 0))
        stroke_img.putalpha(dilated)
        
        result = Image.alpha_composite(stroke_img, img)
        return np.array(result.convert('RGB'))
    
    @staticmethod
    def chroma_key_green(frame: np.ndarray, threshold: int = 140) -> np.ndarray:
        """Remove green screen with tuned parameters"""
        if len(frame.shape) == 2:
            frame = np.stack([frame]*3, axis=2)
        elif frame.shape[2] == 4:
            frame = frame[:, :, :3]
        
        r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
        
        green_intensity = g.astype(float)
        other_intensity = (r.astype(float) + b.astype(float)) / 2
        
        mask = (green_intensity > threshold) & (green_intensity > other_intensity * 1.2)
        
        result = frame.copy()
        result[mask] = [0, 0, 0]
        
        return result

# ═══════════════════════════════════════════════════════════════════════════
# COMPONENT GENERATORS
# ═══════════════════════════════════════════════════════════════════════════

class InfiniteScrollBackground:
    """Generates infinite scrolling background from images"""
    
    def __init__(self, image_paths: List[str], duration: float, speed: int, columns: int = 3, config: VideoConfig = VideoConfig()):
        self.image_paths = image_paths
        self.duration = duration
        self.speed = speed
        self.columns = columns
        self.config = config
        self.canvas = None
        
    def generate_clip(self) -> VideoFileClip:
        if not self.image_paths:
            from moviepy.editor import ColorClip
            return ColorClip(size=(self.config.width, self.config.height), 
                           color=(20, 20, 20), duration=self.duration)
        
        needed_height = int(self.speed * self.duration + self.config.height * 3)
        self.canvas = self._create_canvas(needed_height)
        
        canvas_array = np.array(self.canvas)
        
        def make_frame(t):
            y_pos = int(self.speed * t) % (self.canvas.height - self.config.height)
            y1 = y_pos
            y2 = y1 + self.config.height
            return canvas_array[y1:y2, :, :]
        
        from moviepy.editor import VideoClip
        return VideoClip(make_frame=make_frame, duration=self.duration)
    
    def _create_canvas(self, needed_height: int) -> Image.Image:
        canvas = Image.new('RGB', (self.config.width, needed_height), (0, 0, 0))
        
        columns = self.columns
        gap = self.config.gap_between_images
        item_width = (self.config.width - (columns + 1) * gap) // columns
        item_height = int(item_width * 1.5)  # 2:3 poster ratio
        
        images = []
        for path in self.image_paths:
            try:
                img = Image.open(path).convert('RGB')
                img = ImageOps.fit(img, (item_width, item_height), Image.LANCZOS)
                images.append(img)
            except Exception as e:
                logger.warning(f"Failed to load background asset {path}: {e}")
        
        if not images:
            return canvas
        
        y_offset = gap
        img_index = 0
        
        while y_offset < needed_height:
            x_offset = gap
            for col in range(columns):
                img = images[img_index % len(images)]
                canvas.paste(img, (x_offset, y_offset))
                x_offset += item_width + gap
                img_index += 1
            y_offset += item_height + gap
        
        return canvas

class AssetScanner:
    """Scans and loads assets from directory structure"""
    
    def __init__(self, base_path: str = "assets"):
        self.base_path = Path(base_path)
        self.assets = {
            'backgrounds': [], 'avatars': [], 'movies': [],
            'overlays': [], 'music': [], 'end_cards': [],
            'png_applist': [], 'png_textlist': [], 
            'png_adtext': [], 'png_searchbox': [],
            'png_finger': [], 'png_hd': []
        }
        
    def scan_all(self) -> Dict[str, List[str]]:
        # Sanitization: Guard against deprecated structure logs error but logic removed
        if (self.base_path / 'png_streamapplist').exists():
            msg = "Update Required: 'png_streamapplist' is deprecated. Use 'png_applist/png_textlist'."
            logger.error(msg)
            raise ValueError(msg)
            
        dir_mapping = {
            '0_backgrounds': 'backgrounds',
            'avatars': 'avatars', 'movies': 'movies', 'overlays': 'overlays',
            'music': 'music', 'end_cards': 'end_cards',
            'png_applist': 'png_applist', 'png_textlist': 'png_textlist',
            'png_adtext': 'png_adtext', 'png_searchbox': 'png_searchbox',
            'png_finger': 'png_finger', 'png_hd': 'png_hd'
        }
        
        for dir_name, asset_type in dir_mapping.items():
            dir_path = self.base_path / dir_name
            if dir_path.exists():
                self.assets[asset_type] = self._scan_directory(dir_path, asset_type)
        
        return self.assets
    
    def _scan_directory(self, dir_path: Path, asset_type: str) -> List[str]:
        valid_extensions = {
            'backgrounds': ['.jpg', '.jpeg', '.png', '.webp'],
            'avatars': ['.mp4', '.mov'],
            'movies': ['.mp4', '.mov'],
            'overlays': ['.mp4', '.mov'],
            'music': ['.mp3', '.wav', '.m4a'],
            'end_cards': ['.mp4', '.mov', '.png', '.jpg', '.jpeg'],
            'png_applist': ['.png', '.jpg', '.jpeg'],
            'png_textlist': ['.png', '.jpg', '.jpeg'],
            'png_adtext': ['.png', '.jpg', '.jpeg'],
            'png_searchbox': ['.png', '.jpg', '.jpeg'],
            'png_finger': ['.png'],
            'png_hd': ['.png']
        }
        
        files = []
        exts = valid_extensions.get(asset_type, [])
        
        for file_path in dir_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in exts:
                files.append(str(file_path))
        
        logger.info(f"Found {len(files)} {asset_type} assets")
        return files

# ═══════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════

class DualPhaseGenerator:
    """Main generator for dual-phase viral videos"""
    
    def __init__(self, assets: Dict[str, List[str]], config: VideoConfig = VideoConfig(), seed: Optional[int] = None):
        self.assets = assets
        self.config = config
        self.clips_to_close = []
        
        # Reproducibility
        if seed is not None:
            logger.info(f"Setting random seed to: {seed}")
            random.seed(seed)
            np.random.seed(seed)
        
        # Initial cleanup
        self.force_disk_cleanup()
            
    def force_disk_cleanup(self) -> None:
        """Nuclear cleanup of temporary files in root and output dirs"""
        patterns = ['*.tmp', '.tmp_*', 'temp_*', '*.tmp.mp4']
        search_paths = ['.', 'output']
        
        cleaned_count = 0
        for path in search_paths:
            for pattern in patterns:
                full_pattern = os.path.join(path, pattern)
                for filename in glob.glob(full_pattern):
                    try:
                        os.remove(filename)
                        logger.info(f"🧹 Force cleaned junk file: {filename}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete {filename}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"✨ Nuclear Cleanup: Removed {cleaned_count} junk files")

    def generate(self, 
                 avatar_path: Optional[str] = None, 
                 movie_path: Optional[str] = None, 
                 output_path: str = "output/dual_phase_video.mp4", 
                 video_id: int = 1, 
                 date_str: Optional[str] = None, 
                 loop_music: bool = True, 
                 bgm_volume: Optional[float] = None, 
                 shuffle_backgrounds: bool = True,
                 st_progress_bar: Any = None, 
                 st_status_text: Any = None, 
                 avatar_scale: float = 0.5, 
                 bg_scroll_speed: Optional[int] = None, 
                 avatar_x_offset: Optional[Tuple[int, int]] = None, 
                 bg_grid_cols: Optional[int] = None,
                 machine_tag: Optional[str] = None) -> Dict[str, Any]:
                 
        """Generate the complete dual-phase video"""
        
        # Override config with runtime params if provided
        current_bgm_vol = bgm_volume if bgm_volume is not None else self.config.bgm_volume
        current_scroll_speed = bg_scroll_speed if bg_scroll_speed else self.config.bg_scroll_speed
        current_grid_cols = bg_grid_cols if bg_grid_cols else 3
        
        # Store for internal use
        self.shuffle_backgrounds = shuffle_backgrounds
        self.avatar_scale = avatar_scale
        self.bg_scroll_speed = current_scroll_speed
        self.avatar_x_offset = avatar_x_offset
        self.bg_grid_cols = current_grid_cols
        
        logger.info("\n🎬 Starting Dual-Phase Video Generation...")
        logger.info(f"   🎭 Avatar Scale: {avatar_scale}")
        logger.info(f"   📝 Grid Columns: {current_grid_cols}")
        
        # Selection
        if avatar_path is None: avatar_path = random.choice(self.assets['avatars'])
        if movie_path is None: movie_path = random.choice(self.assets['movies'])
        
        # Filename - Simplified format: MovieAds-MMDD-ID[-TAG]
        if date_str is None:
            from datetime import datetime
            date_str = datetime.now().strftime("%m%d")  # MMDD format (e.g., 0112)
        elif len(date_str) == 8:  # Convert YYYYMMDD to MMDD
            date_str = date_str[4:]
            
        output_dir = Path(output_path).parent
        tag = machine_tag if machine_tag else os.environ.get("ACV_MACHINE_TAG", "")
        tag = str(tag).strip()
        tag_part = f"-{tag}" if tag else ""
        filename = f"MovieAds-{date_str}-{video_id:02d}{tag_part}.mp4"
        final_output_path = str(output_dir / filename)
        temp_output_path = str(output_dir / f".tmp_{filename}")
        
        # Log what's being used (internal tracking only)
        avatar_name = Path(avatar_path).stem
        movie_name = Path(movie_path).stem
        logger.info(f"📹 Avatar: {avatar_name}")
        logger.info(f"🎥 Movie: {movie_name}")
        logger.info(f"📝 Output: {filename}")
        
        try:
            # Generate Phases
            phase_a_clip, phase_a_duration = self.generate_phase_a(avatar_path)
            phase_b_clip, phase_b_duration = self.generate_phase_b(movie_path)
            
            # End Card
            end_card_clip = None
            end_card_duration = 0.0
            if self.assets.get('end_cards'):
                end_card_path = random.choice(self.assets['end_cards'])
                end_card_clip, end_card_duration = self._create_end_card(end_card_path)
                logger.info(f"🎬 Added End Card: {Path(end_card_path).name} ({end_card_duration:.1f}s)")
            
            # Concatenate
            clips = [phase_a_clip, phase_b_clip]
            if end_card_clip: clips.append(end_card_clip)
            
            total_duration = phase_a_duration + phase_b_duration + end_card_duration
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Audio
            final_clip = self.add_global_audio(final_clip, total_duration, loop_music, current_bgm_vol)
            
            # Export
            logger.info(f"\n💾 Exporting to {final_output_path}...")
            
            logger_instance = None
            if st_progress_bar and PROGLOG_AVAILABLE:
                logger_instance = StreamlitLogger(st_progress_bar, st_status_text)
                
            final_clip.write_videofile(
                temp_output_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                threads=4,
                preset='medium',
                logger=logger_instance or 'bar'
            )
            
            # Atomic Rename
            import shutil
            shutil.move(temp_output_path, final_output_path)
            
            # Thumbnail
            thumb_path = self._save_thumbnail(final_clip, final_output_path)
            
            logger.info(f"✅ Video generated successfully!")
            logger.info(f"📊 Total Duration: {total_duration:.1f}s")
            
            return {
                'video_path': final_output_path,
                'thumb_path': thumb_path,
                'components': {'avatar': avatar_name, 'movie': movie_name}
            }
            
        except Exception as e:
            if Path(temp_output_path).exists():
                try: Path(temp_output_path).unlink() 
                except: pass
            logger.error(f"Generation failed: {e}")
            raise
        finally:
            self.cleanup()
            self.force_disk_cleanup()

    def generate_phase_a(self, avatar_path: str) -> Tuple[CompositeVideoClip, float]:
        """Phase A: Digital Human Phase"""
        logger.info("\n🎭 Generating Phase A: Digital Human...")
        
        if avatar_path.endswith('.mov'):
            avatar_clip = VideoFileClip(avatar_path, has_mask=True)
        else:
            avatar_clip = VideoFileClip(avatar_path)
        self.clips_to_close.append(avatar_clip)
        phase_duration = avatar_clip.duration
        
        # Backgrounds
        bg_images = self.assets['backgrounds'].copy()
        if getattr(self, 'shuffle_backgrounds', True):
            random.shuffle(bg_images)
            
        bg_gen = InfiniteScrollBackground(
            bg_images, phase_duration, self.bg_scroll_speed, self.bg_grid_cols, self.config
        )
        bg_clip = bg_gen.generate_clip()
        
        # Searchbox & Collision Logic
        searchbox_clip = None
        searchbox_bottom_y = 0
        if self.assets.get('png_searchbox'):
            searchbox_path = random.choice(self.assets['png_searchbox'])
            searchbox_clip = self._create_searchbox_phase_a(searchbox_path, phase_duration)
            # Default fallback bottom logic handled in method, but explicitly needed for collision
            searchbox_bottom_y = self.config.searchbox_phase_b_y - 5 
            
        # Ad Text
        adtext_clip = None
        adtext_bottom_y = searchbox_bottom_y
        if self.assets.get('png_adtext'):
            path = random.choice(self.assets['png_adtext'])
            # Place below searchbox with small gap
            adtext_y = searchbox_bottom_y + 10
            adtext_clip = self._create_pulsing_adtext(path, phase_duration, y_pos=adtext_y)
            adtext_bottom_y = adtext_y + adtext_clip.size[1]

        # Floating Panels (Left/Right)
        applist_clip = None
        if self.assets.get('png_applist'):
            path = random.choice(self.assets['png_applist'])
            applist_clip = self._create_floating_panel(path, 'left', phase_duration, top_limit=adtext_bottom_y)
            
        textlist_clip = None
        if self.assets.get('png_textlist'):
            path = random.choice(self.assets['png_textlist'])
            textlist_clip = self._create_floating_panel(path, 'right', phase_duration, top_limit=adtext_bottom_y)
            
        # Dynamic Overlays
        logger.info("   🎬 Generating dynamic overlay sequence...")
        overlay_events = self._generate_overlay_events(phase_duration, phase='A')
        
        # Avatar Processing
        x_range = self.avatar_x_offset if self.avatar_x_offset else (-100, 100)
        x_offset = random.randint(x_range[0], x_range[1])
        avatar_clip = self._process_digital_human(avatar_clip, x_offset=x_offset, scale_factor=self.avatar_scale)
        
        # Compositing
        layers = [bg_clip]
        if applist_clip: layers.append(applist_clip)
        if textlist_clip: layers.append(textlist_clip)
        if searchbox_clip: layers.append(searchbox_clip)
        if adtext_clip: layers.append(adtext_clip)
        layers.extend(overlay_events)
        layers.append(avatar_clip)
        
        return CompositeVideoClip(layers, size=(self.config.width, self.config.height)), phase_duration

    def generate_phase_b(self, movie_path: str) -> Tuple[CompositeVideoClip, float]:
        """Phase B: Movie Clip Phase"""
        logger.info("\n🎬 Generating Phase B: Movie Clip...")
        
        movie_clip = VideoFileClip(movie_path)
        self.clips_to_close.append(movie_clip)
        
        # Random subclip
        target_duration = min(random.randint(30, 45), movie_clip.duration)
        max_start = max(0, movie_clip.duration - target_duration)
        start_time = random.uniform(0, max_start)
        movie_clip = movie_clip.subclip(start_time, start_time + target_duration)
        phase_duration = movie_clip.duration
        
        # Background
        bg_images = self.assets['backgrounds'].copy()
        if getattr(self, 'shuffle_backgrounds', True): random.shuffle(bg_images)
        bg_gen = InfiniteScrollBackground(bg_images, phase_duration, self.bg_scroll_speed, self.bg_grid_cols, self.config)
        bg_clip = bg_gen.generate_clip()
        
        # Movie Overlay
        movie_clip = self._resize_to_width(movie_clip, self.config.width)
        movie_clip = movie_clip.set_position(('center', self.config.searchbox_phase_b_y))
        
        # Calculate Layout Metrics for Overlays
        movie_y = self.config.searchbox_phase_b_y
        movie_h = movie_clip.size[1]
        
        searchbox_clip = None
        if self.assets['png_searchbox']:
            path = random.choice(self.assets['png_searchbox'])
            searchbox_clip = self._create_search_box(path, movie_clip, phase_duration)
            
        adtext_clip = None
        adtext_h = 0
        adtext_y = movie_y + movie_h + 10 # Default fallback
        
        if self.assets['png_adtext']:
            path = random.choice(self.assets['png_adtext'])
            adtext_clip = self._create_movie_adtext(path, movie_clip, phase_duration)
            adtext_h = adtext_clip.size[1]
            adtext_y = movie_y + movie_h + 10
            
        hd_clip = None
        if self.assets['png_hd']:
            path = random.choice(self.assets['png_hd'])
            hd_clip = self._create_hd_icon(path, movie_clip, phase_duration)
            
        # Overlays
        logger.info("   🎬 Generating dynamic overlay sequence...")
        layout_info = {
            'movie_y': movie_y,
            'movie_h': movie_h,
            'adtext_y': adtext_y,
            'adtext_h': adtext_h
        }
        overlay_events = self._generate_overlay_events(phase_duration, phase='B', layout_info=layout_info)
        
        layers = [bg_clip, movie_clip]
        if searchbox_clip: layers.append(searchbox_clip)
        if adtext_clip: layers.append(adtext_clip)
        if hd_clip: layers.append(hd_clip)
        layers.extend(overlay_events)
        
        return CompositeVideoClip(layers, size=(self.config.width, self.config.height)), phase_duration

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _process_digital_human(self, avatar_clip: VideoFileClip, x_offset: int, scale_factor: float) -> VideoFileClip:
        # Shrink to 75% as requested
        scale_factor = scale_factor * 0.60
        logger.info(f"   🎭 Processing avatar with scale={scale_factor:.2f}")
        avatar_clip = avatar_clip.resize(scale_factor)

        # Boost avatar volume
        if avatar_clip.audio is not None:
            logger.info("   🔊 Boosting avatar volume (2.0x)")
            avatar_clip = avatar_clip.volumex(2.0)
        
        if not avatar_clip.filename.endswith('.mov'):
            logger.info(f"🎭 Applying green screen removal (thr={self.config.chroma_key_threshold})...")
            avatar_clip = avatar_clip.fx(vfx.mask_color, color=[0, 255, 0], 
                                       thr=self.config.chroma_key_threshold, s=12)
            
        center_x = (self.config.width - avatar_clip.size[0]) // 2
        final_x = center_x + x_offset
        final_y = self.config.height - avatar_clip.size[1]
        
        return avatar_clip.set_position((final_x, final_y))

    def _create_floating_panel(self, image_path: str, side: str, duration: float, top_limit: int = 0) -> ImageClip:
        img_clip = ImageClip(image_path).set_duration(duration)
        
        # Resize panel to 1/3 of screen width
        target_width = self.config.width // 3
        img_clip = img_clip.resize(width=target_width)
        
        # Calculate available vertical space considering top (searchbox) and bottom (avatar) limits
        margin = self.config.floating_panel_margin
        effective_top = max(top_limit + margin, margin)
        effective_bottom = self.config.height - self.config.avatar_safe_zone  # Avoid avatar
        
        available_h = effective_bottom - effective_top
        
        # Center panel in the safe zone between top_limit and avatar_safe_zone
        base_y_target = effective_top + (available_h - img_clip.size[1]) // 2
            
        # Random Y jitter (5-10px range as per requirement)
        jitter = random.randint(5, 10) * random.choice([-1, 1])
        base_y = base_y_target + jitter
        
        if side == 'left': base_x = self.config.floating_panel_margin
        else: base_x = self.config.width - img_clip.size[0] - self.config.floating_panel_margin
        
        def floating_position(t):
            # Use defined amplitude and period
            amp = self.config.floating_panel_amplitude
            period = self.config.floating_panel_period
            float_offset = int(amp * math.sin(2 * math.pi * t / period))
            return (base_x, base_y + float_offset)
            
        return img_clip.set_position(floating_position)

    def _create_pulsing_adtext(self, path: str, duration: float, y_pos: Optional[int] = None) -> ImageClip:
        img_clip = ImageClip(path).set_duration(duration)
        # Sanitization: Use searchbox_padding * 2 (as a generic safe horizontal margin assumption) if exact isn't specified,
        # but logically using safe_zone_margin * 2 is better for general safe areas.
        safe_width = self.config.width - (2 * self.config.safe_zone_margin)
        img_clip = img_clip.resize(width=safe_width) 
        
        if y_pos is not None:
            base_y = y_pos
        else:
            base_y = self.config.height - img_clip.size[1] - 400
            
        img_clip = img_clip.set_position(('center', base_y))
        
        def pulse_resize(get_frame, t):
            frame = get_frame(t)
            scale = 1.0 + self.config.adtext_pulse_scale * math.sin(2 * math.pi * self.config.adtext_pulse_frequency * t)
            
            img = Image.fromarray(frame.astype('uint8'))
            if img.mode == 'RGBA': img = img.convert('RGB')
                
            new_size = (int(img.width * scale), int(img.height * scale))
            img_resized = img.resize(new_size, Image.LANCZOS)
            
            left = (img_resized.width - frame.shape[1]) // 2
            top = (img_resized.height - frame.shape[0]) // 2
            img_cropped = img_resized.crop((left, top, left + frame.shape[1], top + frame.shape[0]))
            
            result = np.array(img_cropped)
            if result.shape[2] == 4: result = result[:, :, :3]
            return result
            
        return img_clip.fl(pulse_resize)

    def _create_searchbox_phase_a(self, path: str, duration: float) -> ImageClip:
        img_clip = ImageClip(path).set_duration(duration)
        img_clip = img_clip.resize(width=min(self.config.width - self.config.searchbox_padding, img_clip.size[0]))
        base_y = self.config.searchbox_phase_b_y - img_clip.size[1] - self.config.searchbox_y_offset
        
        # Random initial jitter
        jitter = random.randint(5, 10) * random.choice([-1, 1])
        base_y += jitter
        
        opacity = random.uniform(self.config.searchbox_opacity_min, self.config.searchbox_opacity_max)
        
        # Floating animation
        def floating_position(t):
            amp = 5  # Subtle 5px float
            period = 4.0  # Slow 4-second cycle
            offset_y = int(amp * math.sin(2 * math.pi * t / period))
            return ('center', base_y + offset_y)
        
        return img_clip.set_position(floating_position).set_opacity(opacity)

    def _create_search_box(self, path: str, movie_clip: VideoFileClip, duration: float) -> ImageClip:
        img_clip = ImageClip(path).set_duration(duration)
        img_clip = img_clip.resize(width=min(self.config.width - self.config.searchbox_padding, img_clip.size[0]))
        base_y = self.config.searchbox_phase_b_y - img_clip.size[1] - self.config.searchbox_y_offset
        
        # Random initial jitter
        jitter = random.randint(5, 10) * random.choice([-1, 1])
        base_y += jitter
        
        opacity = random.uniform(self.config.searchbox_opacity_min, self.config.searchbox_opacity_max)
        
        # Floating animation
        def floating_position(t):
            amp = 5  # Subtle 5px float
            period = 4.0  # Slow 4-second cycle
            offset_y = int(amp * math.sin(2 * math.pi * t / period))
            return ('center', base_y + offset_y)
        
        return img_clip.set_position(floating_position).set_opacity(opacity)
        
    def _create_movie_adtext(self, path: str, movie_clip: VideoFileClip, duration: float) -> ImageClip:
        img_clip = ImageClip(path).set_duration(duration)
        img_clip = img_clip.resize(width=min(self.config.width - self.config.searchbox_padding, img_clip.size[0]))
        
        movie_bottom_y = self.config.searchbox_phase_b_y + movie_clip.size[1]
        pos_y = movie_bottom_y + 10 # 10 px gap
        
        def drift_position(t):
            offset_y = 5 * math.sin(2 * math.pi * 0.5 * t)
            return ('center', pos_y + int(offset_y))
            
        return img_clip.set_position(drift_position)

    def _create_hd_icon(self, path: str, movie_clip: VideoFileClip, duration: float) -> ImageClip:
        img_clip = ImageClip(path).set_duration(duration)
        img_clip = img_clip.resize(height=self.config.hd_icon_height)
        
        movie_width = movie_clip.size[0]
        movie_left_x = (self.config.width - movie_width) // 2
        pos_x = movie_left_x + movie_width - img_clip.size[0] - self.config.hd_icon_padding
        pos_y = self.config.searchbox_phase_b_y + self.config.hd_icon_padding
        
        return img_clip.set_position((pos_x, pos_y)).set_opacity(self.config.hd_icon_opacity)

    def _generate_overlay_events(self, total_duration: float, phase: str = 'B', layout_info: Optional[Dict] = None) -> List[VideoFileClip]:
        events = []
        current_time = 0.25
        
        if not self.assets['overlays']: return events
        
        event_count = 0
        while current_time < total_duration - 2.0:
            event_count += 1
            overlay_path = random.choice(self.assets['overlays'])
            ext = Path(overlay_path).suffix.lower()
            
            if ext in ['.mp4', '.mov']:
                overlay_clip = VideoFileClip(overlay_path, has_mask=True).without_audio()
                self.clips_to_close.append(overlay_clip)
                overlay_duration = min(overlay_clip.duration, total_duration - current_time)
                
                try:
                    if overlay_clip.mask is None:
                         overlay_clip = overlay_clip.fx(vfx.mask_color, color=[0, 0, 0], thr=40, s=10)
                except:
                     overlay_clip = overlay_clip.fx(vfx.mask_color, color=[0, 0, 0], thr=40, s=10)
            else:
                overlay_duration = min(random.uniform(3.0, 5.0), total_duration - current_time)
                overlay_clip = ImageClip(overlay_path).set_duration(overlay_duration)
            
            overlay_clip = overlay_clip.resize(width=int(self.config.width * self.config.overlay_width_ratio))
            overlay_clip = overlay_clip.set_duration(overlay_duration)
            
            # Positioning
            if phase == 'A':
                overlay_x = (self.config.width - overlay_clip.size[0]) // 2
                center_y = (self.config.height - overlay_clip.size[1]) // 2
                overlay_y = center_y + random.randint(-5, 5)
            elif layout_info:
                 # New logic for Phase B with layout info: 6 random zones
                 zone = random.choice(range(6))
                 movie_y = layout_info.get('movie_y', 250)
                 movie_h = layout_info.get('movie_h', 600)
                 adtext_y = layout_info.get('adtext_y', movie_y + movie_h + 10)
                 adtext_h = layout_info.get('adtext_h', 100)
                 
                 # Zones 0-2: Movie (Left, Center, Right)
                 # Zones 3-5: Below Adtext (Left, Center, Right)
                 
                 if zone < 3: # Movie zones
                     # Ensure overlay fits within movie height
                     if overlay_clip.size[1] > movie_h:
                         overlay_clip = overlay_clip.resize(height=movie_h)

                     target_y_min = movie_y
                     target_y_max = movie_y + movie_h - overlay_clip.size[1]
                     if target_y_max < target_y_min: target_y_max = target_y_min
                     
                     overlay_y = random.randint(target_y_min, target_y_max)
                     
                     if zone == 0: # Left
                         overlay_x = self.config.safe_zone_margin
                     elif zone == 1: # Center
                         overlay_x = (self.config.width - overlay_clip.size[0]) // 2
                     else: # Right
                         overlay_x = self.config.width - overlay_clip.size[0] - self.config.safe_zone_margin
                         
                 else: # Below Adtext zones
                     target_y_min = adtext_y + adtext_h + 10 
                     target_y_max = min(self.config.height - overlay_clip.size[1] - 50, target_y_min + 300)
                     if target_y_max < target_y_min: target_y_max = target_y_min
                     
                     overlay_y = random.randint(target_y_min, target_y_max)
                     
                     if zone == 3: # Left
                         overlay_x = self.config.safe_zone_margin
                     elif zone == 4: # Center
                         overlay_x = (self.config.width - overlay_clip.size[0]) // 2
                     else: # Right
                         overlay_x = self.config.width - overlay_clip.size[0] - self.config.safe_zone_margin

            else:
                safe_x_min = self.config.safe_zone_margin
                safe_x_max = max(safe_x_min + 50, self.config.width - overlay_clip.size[0] - safe_x_min - 100)
                safe_y_min = self.config.safe_zone_margin + 150
                safe_y_max = max(safe_y_min + 50, self.config.height - overlay_clip.size[1] - safe_x_min - 150)
                overlay_x = random.randint(safe_x_min, safe_x_max)
                overlay_y = random.randint(safe_y_min, safe_y_max)
                
            overlay_clip = overlay_clip.set_start(current_time).set_position((overlay_x, overlay_y))
            overlay_clip = overlay_clip.set_opacity(random.uniform(self.config.overlay_opacity_min, self.config.overlay_opacity_max))
            events.append(overlay_clip)
            
            # Finger Tap
            if self.assets['png_finger']:
                finger_path = random.choice(self.assets['png_finger'])
                finger_clip = ImageClip(finger_path).set_duration(overlay_duration)
                finger_clip = finger_clip.resize(height=self.config.finger_target_height)
                
                finger_base_x = overlay_x + overlay_clip.size[0] - int(finger_clip.size[0] * 0.7)
                finger_base_y = int(overlay_y + (overlay_clip.size[1] * 0.66) - (finger_clip.size[1] * 0.2))
                
                def make_tap_position(base_x, base_y):
                    def tap_position(t):
                        # Use config logic for frequency/amplitude if desired
                        amp = self.config.finger_tap_amplitude
                        freq = self.config.finger_tap_frequency
                        offset_y = amp * math.sin(freq * t)
                        return (base_x, base_y + int(offset_y))
                    return tap_position
                    
                finger_clip = finger_clip.set_start(current_time)
                finger_clip = finger_clip.set_position(make_tap_position(finger_base_x, finger_base_y))
                finger_clip = finger_clip.set_opacity(0.9)
                events.append(finger_clip)
                
            logger.info(f"   📍 Event {event_count}: {Path(overlay_path).name} at t={current_time:.1f}s")
            current_time += overlay_duration + random.uniform(self.config.overlay_gap_min, self.config.overlay_gap_max)
            
        return events

    def _create_end_card(self, path: str, default_duration: float = 5.0) -> Tuple[Any, float]:
        ext = Path(path).suffix.lower()
        if ext in ['.mp4', '.mov']:
            clip = VideoFileClip(path)
            self.clips_to_close.append(clip)
            duration = clip.duration
        else:
            clip = ImageClip(path).set_duration(default_duration)
            duration = default_duration
        return clip.resize(newsize=(self.config.width, self.config.height)), duration

    def add_global_audio(self, video_clip: CompositeVideoClip, total_duration: float, loop_music: bool = True, volume: float = 0.4) -> CompositeVideoClip:
        if not self.assets['music']: return video_clip
        music_path = random.choice(self.assets['music'])
        logger.info(f"🎵 Adding BGM: {Path(music_path).name}")
        
        bgm_clip = AudioFileClip(music_path)
        self.clips_to_close.append(bgm_clip)
        
        if loop_music and bgm_clip.duration < total_duration:
            bgm_clip = bgm_clip.loop(duration=total_duration)
        else:
            bgm_clip = bgm_clip.subclip(0, min(bgm_clip.duration, total_duration))
            
        bgm_clip = bgm_clip.volumex(volume)
        
        if video_clip.audio:
            final_audio = CompositeAudioClip([video_clip.audio, bgm_clip])
        else:
            final_audio = bgm_clip
            
        return video_clip.set_audio(final_audio)

    def _resize_to_width(self, clip: VideoFileClip, target_width: int) -> VideoFileClip:
        if clip.size[0] == target_width: return clip
        return clip.resize(target_width / clip.size[0])

    def _save_thumbnail(self, clip: CompositeVideoClip, video_path: str) -> Optional[str]:
        thumb_path = str(Path(video_path).with_suffix('.jpg'))
        try:
            target_time = 0.1
            if clip.duration < 0.2: target_time = 0.0
            
            logger.info(f"   🖼️ Generating thumbnail at t={target_time}s...")
            frame = clip.get_frame(target_time)
            Image.fromarray(frame.astype('uint8')).save(thumb_path, 'JPEG', quality=85)
            
            if Path(thumb_path).exists():
                logger.info(f"🖼️  Thumbnail saved: {Path(thumb_path).name}")
            return thumb_path
        except Exception as e:
            logger.error(f"Failed to save thumbnail: {e}")
            return None

    def cleanup(self) -> None:
        for clip in self.clips_to_close:
            try: clip.close() 
            except Exception as e: 
                logger.warning(f"Error closing clip: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    setup_logging()
    logger.info("=" * 70)
    logger.info(f"🎬 DUAL-PHASE VIRAL VIDEO GENERATOR v{__version__}")
    logger.info("=" * 70)
    
    config = VideoConfig()
    logger.info(f"⚙️  BGM Volume: {config.bgm_volume}")

    scanner = AssetScanner()
    try:
        assets = scanner.scan_all()
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return

    # Check Required
    for req in config.validation_required:
        if not assets[req]:
            logger.error(f"❌ ERROR: No {req} found!")
            return

    generator = DualPhaseGenerator(assets, config, seed=42)
    # Default params are now handled by Config inside the class unless overridden
    generator.generate()

if __name__ == "__main__":
    Path("output").mkdir(exist_ok=True)
    main()
