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
    CompositeAudioClip, concatenate_videoclips, concatenate_audioclips, vfx
)
from moviepy.audio.fx import all as afx
from src.assets import scan_assets
from src.media_io import configure_ffmpeg, load_video_clip

# Import proglog for custom MoviePy progress logging
try:
    from proglog import ProgressBarLogger
    PROGLOG_AVAILABLE = True
except ImportError:
    PROGLOG_AVAILABLE = False

# Robustness: Absolute Path Anchor
BASE_DIR = Path(__file__).parent.resolve()

def safe_random_choice(assets_list: List[str]) -> Optional[str]:
    """Select a random asset with basic validation."""
    if not assets_list:
        return None
    choice = random.choice(assets_list)
    if os.path.getsize(choice) <= 0:
        raise ValueError(f"Invalid asset (0 bytes): {choice}")
    return choice



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
    """Generates infinite scrolling background dynamically (Low Memory, Seamless)"""
    
    def __init__(self, image_paths: List[str], duration: float, speed: int, columns: int = 3, config: VideoConfig = VideoConfig(), start_time: float = 0.0):
        self.image_paths = image_paths
        self.duration = duration
        self.speed = speed
        self.columns = columns
        self.config = config
        self.start_time = start_time
        
        # Pre-calculate metrics
        self.gap = self.config.gap_between_images
        self.item_width = (self.config.width - (self.columns + 1) * self.gap) // self.columns
        self.item_height = int(self.item_width * 1.5)  # 2:3 ratio
        self.row_height = self.item_height + self.gap
        
        # Pre-load and resize ALL images (to avoid IO during render)
        self.images: List[Image.Image] = []
        self._preload_images()
        
    def _preload_images(self):
        """Pre-resize images to target dimensions"""
        if not self.image_paths: return
        
        for path in self.image_paths:
            try:
                img = Image.open(path).convert('RGB')
                img = ImageOps.fit(img, (self.item_width, self.item_height), Image.LANCZOS)
                self.images.append(img)
            except Exception as e:
                raise ValueError(f"Failed to load BG asset {path}: {e}")
                
    def generate_clip(self) -> VideoFileClip:
        if not self.images:
            from moviepy.editor import ColorClip
            return ColorClip(size=(self.config.width, self.config.height), 
                           color=(20, 20, 20), duration=self.duration)
        
        w, h = self.config.width, self.config.height
        cols = self.columns
        gap = self.gap
        row_h = self.row_height
        
        num_images = len(self.images)
        
        def make_frame(t):
            # Calculate global vertical offset
            current_time = self.start_time + t
            global_y = int(self.speed * current_time)
            
            # Create base frame
            frame = Image.new('RGB', (w, h), (0,0,0))
            
            # Determine first visible row index
            # global_y corresponds to the pixel that is at TOP of screen (y=0)
            # So first visible row is the one containing global_y
            start_row_idx = global_y // row_h
            
            # We need to draw enough rows to fill screen height
            # Each row is row_h. Screen is h.
            # We need ceil(h / row_h) + 1 rows
            rows_to_draw = (h // row_h) + 2
            
            # Y-coordinate of the top of the start_row relative to screen top
            # relative_y = (start_row_idx * row_h) - global_y
            # This will be <= 0
            relative_y = (start_row_idx * row_h) - global_y
            
            current_row = start_row_idx
            draw_y = relative_y
            
            for _ in range(rows_to_draw):
                x_off = gap
                for c in range(cols):
                    # Calculate image index conceptually
                    # Row 0 has images 0..cols-1
                    # Row R has images R*cols .. R*cols + cols - 1
                    img_global_idx = (current_row * cols) + c
                    
                    # Wrap around list of images
                    img = self.images[img_global_idx % num_images]
                    
                    frame.paste(img, (x_off, draw_y))
                    x_off += self.item_width + gap
                
                draw_y += row_h
                current_row += 1
                
            return np.array(frame)
        
        from moviepy.editor import VideoClip
        return VideoClip(make_frame=make_frame, duration=self.duration)

class AssetScanner:
    """Scans and loads assets from directory structure"""
    
    def __init__(self, base_path: Union[str, Path] = "assets"):
        if not os.path.isabs(str(base_path)):
            self.base_path = BASE_DIR / base_path
        else:
            self.base_path = Path(base_path)
        
    def scan_all(self) -> Dict[str, List[str]]:
        if (self.base_path / 'png_streamapplist').exists():
            msg = "Update Required: 'png_streamapplist' is deprecated. Use 'png_applist/png_textlist'."
            logger.error(msg)
            raise ValueError(msg)

        return scan_assets(self.base_path)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════

class DualPhaseGenerator:
    """Main generator for dual-phase viral videos"""
    
    def __init__(self, assets: Dict[str, List[str]], config: VideoConfig = VideoConfig(), seed: Optional[int] = None):
        self.assets = assets
        self.config = config
        self.clips_to_close = []
        self.ffmpeg_path = configure_ffmpeg()
        logger.info(f"Using ffmpeg: {self.ffmpeg_path}")
        self._fixed_seed = seed
        self._last_bg_signature: Optional[Tuple[str, ...]] = None
        self._last_pair: Optional[Tuple[str, str]] = None
        
        # Reproducibility
        if seed is not None:
            logger.info(f"Setting random seed to: {seed}")
            random.seed(seed)
            np.random.seed(seed)
        
        # Initial cleanup
        self.force_disk_cleanup()
        
        # Global Background State (Per Generation)
        self.current_bg_images = []
        self.current_bg_cols = 3
        
        # History Tracking
        self.history_file = BASE_DIR / "history.json"
        self.history = self._load_history()

    def _reseed_rng_if_needed(self) -> None:
        """Ensure non-deterministic randomness per generation unless seed is fixed."""
        if self._fixed_seed is not None:
            return
        entropy = int.from_bytes(os.urandom(8), "big")
        random.seed(entropy)
        np.random.seed(entropy & 0xFFFFFFFF)
        logger.info(f"🔀 RNG reseeded: {entropy}")

    def _load_history(self) -> List[Dict]:
        if self.history_file.exists():
            try:
                import json
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_history(self, avatar: str, movie: str):
        import json
        from datetime import datetime
        entry = {
            "avatar": avatar,
            "movie": movie,
            "timestamp": datetime.now().isoformat()
        }
        self.history.append(entry)
        # Keep last 100 records
        if len(self.history) > 100:
            self.history = self.history[-100:]
            
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _check_history(self, avatar: str, movie: str) -> bool:
        """Check if pair exists in last 50 records"""
        # Look at last 50
        recent = self.history[-50:]
        for entry in recent:
            if entry['avatar'] == avatar and entry['movie'] == movie:
                return True
        return False
            
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
                 avatar_path_in: Optional[str] = None, 
                 movie_path_in: Optional[str] = None, 
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
                 machine_tag: Optional[str] = None,
                 template_id: str = "dec2025") -> Dict[str, Any]:
                 
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
        self._reseed_rng_if_needed()
        
        # Selection with De-duplication Logic
        # Try up to 10 times to find a unique pair
        avatar_path = None
        movie_path = None
        
        if avatar_path_in and movie_path_in:
             avatar_path = avatar_path_in
             movie_path = movie_path_in
        else:
             for attempt in range(10):
                 # Pick candidates
                 cand_avatar = avatar_path_in if avatar_path_in else random.choice(self.assets['avatars'])
                 cand_movie = movie_path_in if movie_path_in else random.choice(self.assets['movies'])
                 
                 cand_avatar_name = Path(cand_avatar).name
                 cand_movie_name = Path(cand_movie).name
                 
                 if self._last_pair and (cand_avatar_name, cand_movie_name) == self._last_pair:
                     logger.warning(f"⚠️ Immediate duplicate pair (Attempt {attempt+1}): {cand_avatar_name} + {cand_movie_name}. Re-rolling...")
                     continue
                 
                 if not self._check_history(cand_avatar_name, cand_movie_name):
                     avatar_path = cand_avatar
                     movie_path = cand_movie
                     break
                 else:
                     logger.warning(f"⚠️ Duplicate Pair found (Attempt {attempt+1}): {cand_avatar_name} + {cand_movie_name}. Re-rolling...")
            
             if avatar_path is None:
                 avatar_path = cand_avatar
                 movie_path = cand_movie
                 logger.warning("⚠️ Could not find unique pair after 10 attempts. Using last roll.")
        
        # Filename
        if date_str is None:
            from datetime import datetime
            date_str = datetime.now().strftime("%m%d")
        elif len(date_str) == 8:
            date_str = date_str[4:]
            
        output_dir = Path(output_path).parent
        tag = machine_tag if machine_tag else os.environ.get("ACV_MACHINE_TAG", "")
        tag = str(tag).strip()
        tag_part = f"-{tag}" if tag else ""
        filename = f"{date_str}-{video_id:02d}{tag_part}.mp4"
        final_output_path = str(output_dir / filename)
        temp_output_path = str(output_dir / f".tmp_{filename}")
        
        avatar_name = Path(avatar_path).stem
        movie_name = Path(movie_path).stem
        logger.info(f"📹 Avatar: {avatar_name}")
        logger.info(f"🎥 Movie: {movie_name}")
        logger.info(f"📝 Output: {filename}")
        
        self._save_history(Path(avatar_path).name, Path(movie_path).name)
        self._last_pair = (Path(avatar_path).name, Path(movie_path).name)
        
        try:
            # Initialize Global Background State (Per Run)
            if self.assets['backgrounds']:
                # Shuffle ONCE, avoid repeating exact order
                bg_list = self.assets['backgrounds'].copy()
                if self.shuffle_backgrounds and len(bg_list) > 1:
                    sig = None
                    for _ in range(5):
                        random.shuffle(bg_list)  # User wants random order every time
                        sig = tuple(bg_list)
                        if sig != self._last_bg_signature:
                            break
                    if sig is not None:
                        self._last_bg_signature = sig
                else:
                    bg_list.sort()
                self.current_bg_images = bg_list
                # Random Columns 3-5
                self.current_bg_cols = random.randint(3, 5)
                logger.info(f"🎨 Global Background: {len(bg_list)} images, {self.current_bg_cols} columns")
            else:
                self.current_bg_images = []
                self.current_bg_cols = 3

            # Select Template Strategy
            if template_id == "feb2026":
                strategy = Feb2026Template(self)
            else:
                strategy = Dec2025Template(self)
                
            # Opening Sequence
            opening_clip = None
            current_bg_time = 0.0
            
            if st_status_text: st_status_text.text("Generating Opening Sequence...")
            opening_clip = strategy.create_opening_sequence(bg_start_time=current_bg_time)
            
            if opening_clip:
                current_bg_time += opening_clip.duration

            # Generate Phases
            phase_a_clip, phase_a_duration = strategy.create_phase_a(avatar_path, bg_start_time=current_bg_time)
            current_bg_time += phase_a_duration
            
            phase_b_clip, phase_b_duration = strategy.create_phase_b(movie_path, bg_start_time=current_bg_time)
            current_bg_time += phase_b_duration
            
            # End Card
            end_card_clip = None
            end_card_duration = 0.0
            if self.assets.get('end_cards'):
                end_card_path = safe_random_choice(self.assets['end_cards'])
                if end_card_path:
                    end_card_clip, end_card_duration = self._create_end_card(end_card_path)
                    logger.info(f"🎬 Added End Card: {Path(end_card_path).name} ({end_card_duration:.1f}s)")
            
            # Concatenate main phases
            clips = [phase_a_clip, phase_b_clip]
            if end_card_clip:
                clips.append(end_card_clip)
            
            total_duration = phase_a_duration + phase_b_duration + end_card_duration
            main_clip = concatenate_videoclips(clips, method="compose")
            
            # Audio: mix speech/movie audio with BGM
            bgm_clip = self._prepare_bgm(total_duration, loop_music, current_bgm_vol)
            main_audio = main_clip.audio
            if bgm_clip:
                if main_audio:
                    main_audio = CompositeAudioClip([main_audio, bgm_clip])
                else:
                    main_audio = bgm_clip
            if main_audio:
                main_clip = main_clip.set_audio(main_audio)
            
            if opening_clip:
                final_video = concatenate_videoclips([opening_clip, main_clip])
                opening_audio = opening_clip.audio
                if opening_audio and main_audio:
                    final_audio = CompositeAudioClip([
                        opening_audio.set_start(0),
                        main_audio.set_start(opening_clip.duration)
                    ])
                elif opening_audio:
                    final_audio = opening_audio
                elif main_audio:
                    final_audio = main_audio.set_start(opening_clip.duration)
                else:
                    final_audio = None
                if final_audio:
                    final_video = final_video.set_audio(final_audio)
                final_clip = final_video
            else:
                final_clip = main_clip
            
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
                threads=4, # Safe default
                preset='medium',
                logger=logger_instance or 'bar'
            )
            
            # Atomic Rename
            import shutil
            shutil.move(temp_output_path, final_output_path)
            
            # Thumbnail
            # Change: Capture first frame of Digital Human (Phase A)
            # If opening exists, skip opening_duration.
            thumb_seek = 0.1
            if opening_clip:
                thumb_seek = opening_clip.duration + 0.1
                
            # Ensure we don't seek past end
            if thumb_seek >= final_clip.duration:
                thumb_seek = max(0, final_clip.duration - 0.5)
                
            thumb_path = self._save_thumbnail(final_clip, final_output_path, seek_time=thumb_seek)
            
            logger.info(f"✅ Video generated successfully!")
            logger.info(f"📊 Total Duration: {final_clip.duration:.1f}s")
            
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



    def generate_phase_a_legacy_logic(self, avatar_path: str) -> Tuple[CompositeVideoClip, float]:
        """Legacy Logic (Dec 2025) for Phase A"""
        logger.info("\n🎭 Generating Phase A (Dec 2025)...")
        # Reuse helper to prepare base environment
        bg_clip, avatar_clip, phase_duration = self._prepare_phase_a_base(avatar_path)
        
        layers = [bg_clip]
        
        # --- DEC 2025 Logic ---
        # Searchbox & Collision Logic
        searchbox_clip = None
        searchbox_bottom_y = 0
        if self.assets.get('png_searchbox'):
            # Retry logic
            searchbox_path = safe_random_choice(self.assets['png_searchbox'])
            if searchbox_path:
                searchbox_clip = self._create_searchbox_phase_a(searchbox_path, phase_duration)
                searchbox_bottom_y = self.config.searchbox_phase_b_y - 5 
                layers.append(searchbox_clip)
            
        # Ad Text
        adtext_clip = None
        adtext_bottom_y = searchbox_bottom_y
        if self.assets.get('png_adtext'):
            path = safe_random_choice(self.assets['png_adtext'])
            if path:
                adtext_y = searchbox_bottom_y + 10
                adtext_clip = self._create_pulsing_adtext(path, phase_duration, y_pos=adtext_y)
                adtext_bottom_y = adtext_y + adtext_clip.size[1]
                layers.append(adtext_clip)

        # Floating Panels (Left/Right)
        if self.assets.get('png_applist'):
            path = safe_random_choice(self.assets['png_applist'])
            if path:
                applist_clip = self._create_floating_panel(path, 'left', phase_duration, top_limit=adtext_bottom_y)
                layers.append(applist_clip)
            
        if self.assets.get('png_textlist'):
            path = safe_random_choice(self.assets['png_textlist'])
            if path:
                textlist_clip = self._create_floating_panel(path, 'right', phase_duration, top_limit=adtext_bottom_y)
                layers.append(textlist_clip)
            
        # Dynamic Overlays
        logger.info("   🎬 Generating dynamic overlay sequence...")
        overlay_events = self._generate_overlay_events(phase_duration, phase='A')
        layers.extend(overlay_events)
        
        layers.append(avatar_clip)
        phase_clip = CompositeVideoClip(layers, size=(self.config.width, self.config.height))
        if avatar_clip.audio:
            phase_clip = phase_clip.set_audio(avatar_clip.audio)
        return phase_clip, phase_duration

    def generate_phase_a_feb2026_logic(self, avatar_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        """Feb 2026 Logic: Background -> Avatar -> UI -> Floating"""
        
        # 1. Prepare Base - Load Avatar
        has_mask = avatar_path.endswith('.mov')
        avatar_clip = self._safe_load_video_clip(avatar_path, has_mask=has_mask)
        self.clips_to_close.append(avatar_clip)
        
        # Keep original playback speed to preserve natural voice
        speed_factor = 1.0
        phase_duration = avatar_clip.duration
        
        # Audio Boost
        if avatar_clip.audio:
            avatar_clip = avatar_clip.set_audio(avatar_clip.audio.volumex(2.0))
            
        screen_w, screen_h = self.config.width, self.config.height
        layers = []
        
        # 2. Global Background (Seamless)
        bg_gen = InfiniteScrollBackground(
            self.current_bg_images, 
            phase_duration, 
            self.config.bg_scroll_speed, 
            self.current_bg_cols, 
            self.config,
            start_time=bg_start_time
        )
        bg_clip = bg_gen.generate_clip()
        layers.append(bg_clip)
        
        # 3. Avatar (Bottom Center + Random Offset/Scale)
        # Scale: 0.6 - 0.8 random
        scale = random.uniform(0.6, 0.8)
        avatar_clip = avatar_clip.resize(height=int(screen_h * scale))
        
        # Position: Bottom Center + Random X (+/- 100)
        x_offset = random.randint(-100, 100)
        av_w, av_h = avatar_clip.size
        av_x = (screen_w - av_w) // 2 + x_offset
        av_y = screen_h - av_h + 50 # +50 to hide bottom gap
        
        avatar_clip = avatar_clip.set_position((av_x, av_y))
        layers.append(avatar_clip)
        
        # 4. UI Layer (Below Overlay)
        # Searchbox (Top Center)
        sb_h = 0
        if self.assets['png_searchbox']:
            sb_path = safe_random_choice(self.assets['png_searchbox'])
            if sb_path:
                sb_clip = ImageClip(sb_path).set_duration(phase_duration)
                sb_clip = self._resize_to_width(sb_clip, screen_w)
                sb_clip = sb_clip.set_position(('center', 0))
                layers.append(sb_clip)
                sb_h = sb_clip.size[1]
                
        # AppList (Left Side, Opacity 90%)
        if self.assets['png_applist']:
            app_path = safe_random_choice(self.assets['png_applist'])
            if app_path:
                app_clip = self._create_floating_panel(app_path, side='left', duration=phase_duration, top_limit=250)
                app_clip = app_clip.set_opacity(0.9)
                layers.append(app_clip)
                
        # AdText (Bottom Center, Opacity 90%)
        if self.assets['png_adtext']:
            ad_path = safe_random_choice(self.assets['png_adtext'])
            if ad_path:
                ad_clip = ImageClip(ad_path).set_duration(phase_duration)
                ad_clip = self._resize_to_width(ad_clip, int(screen_w * 0.8))
                # Position around 3/4 of screen height
                ad_y = int(screen_h * 0.75)
                # Clamp to keep within screen
                ad_y = min(ad_y, screen_h - ad_clip.size[1] - 10)
                ad_clip = ad_clip.set_position(('center', ad_y)).set_opacity(0.9)
                layers.append(ad_clip)
                
        # 5. Floating Layer (Right-Middle Overlay, below Searchbox)
        if self.assets['overlays']:
             cta_path = safe_random_choice(self.assets['overlays'])
             if cta_path:
                 # Overlay Clip - Robust Loading
                 cta_clip = self._load_overlay_clip(cta_path)
                 
                 # Calculate Duration (Start at 2.0s)
                 cta_start_time = 2.0
                 remaining_duration = phase_duration - cta_start_time
                 
                 if remaining_duration > 0:
                     safe_duration = self._safe_clip_duration(cta_clip, remaining_duration)
                     if safe_duration <= 0:
                         return CompositeVideoClip(layers, size=(screen_w, screen_h)), phase_duration
                     if cta_clip.duration < safe_duration:
                         cta_clip = vfx.loop(cta_clip, duration=safe_duration)
                     else:
                         cta_clip = cta_clip.subclip(0, safe_duration)
                     self.clips_to_close.append(cta_clip)
                 
                     # Position: Right-Middle, below Searchbox
                     # Avoid blocking AppList (Left) - Guaranteed by being on Right
                     # Scale? Original size or fit? Assume original but ensure fits width
                     if cta_clip.size[0] > screen_w * 0.5:
                         cta_clip = self._resize_to_width(cta_clip, int(screen_w * 0.45))
                     # Keep overlay just below searchbox in upper-right band
                     cta_y = sb_h + 10
                     max_bottom = int(screen_h * 0.5)
                     available_h = max_bottom - cta_y
                     if available_h < 120:
                         max_bottom = int(screen_h * 0.6)
                         available_h = max_bottom - cta_y
                     if cta_clip.size[1] > available_h:
                         cta_clip = cta_clip.resize(height=max(120, available_h))
                     
                     cta_x = max(self.config.safe_zone_margin, screen_w - cta_clip.size[0] - self.config.safe_zone_margin)
                     # Clamp within screen
                     cta_y = max(10, min(cta_y, screen_h - cta_clip.size[1] - 10))
                     
                     # Apply Start Time & Opacity
                     cta_clip = cta_clip.set_start(cta_start_time).set_position((cta_x, cta_y)).set_opacity(random.uniform(0.6, 0.7))
                     layers.append(cta_clip)
                     
                     # Small Searchbox inside Overlay
                     if self.assets['png_searchbox']:
                         small_sb_path = safe_random_choice(self.assets['png_searchbox'])
                         if small_sb_path:
                             small_sb = ImageClip(small_sb_path).set_duration(safe_duration)
                             small_sb = small_sb.set_start(cta_start_time)
                             
                             # Width = 3/4 of Overlay
                             target_w = int(cta_clip.size[0] * 0.75)
                             small_sb = self._resize_to_width(small_sb, target_w)
                             
                             # Center inside Overlay
                             ssb_x = cta_x + (cta_clip.size[0] - target_w) // 2
                             ssb_y = cta_y + (cta_clip.size[1] - small_sb.size[1]) // 2
                             
                             small_sb = small_sb.set_position((ssb_x, ssb_y))
                             layers.append(small_sb)
                             
                             # Finger (Bottom Right of Overlay)
                             if self.assets['png_finger']:
                                 f_path = safe_random_choice(self.assets['png_finger'])
                                 if f_path:
                                     finger_img = ImageClip(f_path).set_duration(safe_duration)
                                     finger_img = finger_img.set_start(cta_start_time)
                                     
                                     # Resize to match small searchbox width (3/4 overlay)
                                     finger_img = self._resize_to_width(finger_img, target_w)
                                     
                                     # Position: Overlay Bottom Right (clamped to screen)
                                     f_x = cta_x + cta_clip.size[0] - finger_img.size[0] // 2
                                     f_y = cta_y + cta_clip.size[1] - finger_img.size[1] // 2
                                     f_x = min(max(0, f_x), screen_w - finger_img.size[0])
                                     f_y = min(max(0, f_y), screen_h - finger_img.size[1])
                                     
                                     # Pulse Animation
                                     finger_img = finger_img.resize(lambda t: 1.0 + 0.1 * (math.sin(t*5)**2))
                                     finger_img = finger_img.set_position((f_x, f_y))
                                     layers.append(finger_img)

        phase_clip = CompositeVideoClip(layers, size=(screen_w, screen_h))
        if avatar_clip.audio:
            phase_clip = phase_clip.set_audio(avatar_clip.audio)
        return phase_clip, phase_duration

    def _prepare_phase_a_base(self, avatar_path: str):
        """Helper to prepare common Phase A elements"""
        # Load Avatar (helper)
        has_mask = avatar_path.endswith('.mov')
        avatar_clip = self._safe_load_video_clip(avatar_path, has_mask=has_mask)
        self.clips_to_close.append(avatar_clip)
        phase_duration = avatar_clip.duration
        
        bg_images = self.assets['backgrounds'].copy()
        if getattr(self, 'shuffle_backgrounds', True): 
            random.shuffle(bg_images)
        else:
            bg_images.sort() # Ensure deterministic start (poster_0, poster_1...)
        bg_gen = InfiniteScrollBackground(bg_images, phase_duration, self.bg_scroll_speed, self.bg_grid_cols, self.config)
        bg_clip = bg_gen.generate_clip()
        
        x_range = self.avatar_x_offset if self.avatar_x_offset else (-100, 100)
        x_offset = random.randint(x_range[0], x_range[1])
        avatar_clip = self._process_digital_human(avatar_clip, x_offset=x_offset, scale_factor=self.avatar_scale)
        
        return bg_clip, avatar_clip, phase_duration

    def generate_phase_b_legacy_logic(self, movie_path: str) -> Tuple[CompositeVideoClip, float]:
        """Legacy Logic (Dec 2025) for Phase B"""
        logger.info("\n🎬 Generating Phase B (Dec 2025)...")
        bg_clip, movie_clip, phase_duration = self._prepare_phase_b_base(movie_path)
        
        layers = [bg_clip, movie_clip]
        
        # Calculate Layout Metrics for Overlays
        movie_y = self.config.searchbox_phase_b_y
        movie_h = movie_clip.size[1]
        
        searchbox_clip = None
        if self.assets['png_searchbox']:
            path = safe_random_choice(self.assets['png_searchbox'])
            if path:
                searchbox_clip = self._create_search_box(path, movie_clip, phase_duration)
                layers.append(searchbox_clip)
            
        adtext_clip = None
        adtext_h = 0
        adtext_y = movie_y + movie_h + 10
        
        if self.assets['png_adtext']:
            path = safe_random_choice(self.assets['png_adtext'])
            if path:
                adtext_clip = self._create_movie_adtext(path, movie_clip, phase_duration)
                adtext_h = adtext_clip.size[1]
                adtext_y = movie_y + movie_h + 10
                layers.append(adtext_clip)
            
        hd_clip = None
        if self.assets['png_hd']:
            path = safe_random_choice(self.assets['png_hd'])
            if path:
                hd_clip = self._create_hd_icon(path, movie_clip, phase_duration)
                layers.append(hd_clip)
            
        # Overlays
        logger.info("   🎬 Generating dynamic overlay sequence...")
        layout_info = {
            'movie_y': movie_y,
            'movie_h': movie_h,
            'adtext_y': adtext_y,
            'adtext_h': adtext_h
        }
        overlay_events = self._generate_overlay_events(phase_duration, phase='B', layout_info=layout_info)
        layers.extend(overlay_events)
        
        phase_clip = CompositeVideoClip(layers, size=(self.config.width, self.config.height))
        if movie_clip.audio:
            phase_clip = phase_clip.set_audio(movie_clip.audio)
        return phase_clip, phase_duration

    def _prepare_phase_b_base(self, movie_path: str):
        """Helper to prepare common Phase B elements (Clip + Background)"""
        # Load Movie (Legacy Phase B)
        movie_clip = self._safe_load_video_clip(movie_path)
        self.clips_to_close.append(movie_clip)
        
        # Random subclip
        target_duration = min(random.randint(30, 45), movie_clip.duration)
        max_start = max(0, movie_clip.duration - target_duration)
        start_time = random.uniform(0, max_start)
        movie_clip = movie_clip.subclip(start_time, start_time + target_duration)
        phase_duration = movie_clip.duration
        
        # Background
        bg_images = self.assets['backgrounds'].copy()
        if getattr(self, 'shuffle_backgrounds', True): 
            random.shuffle(bg_images)
        else:
            bg_images.sort() # Ensure deterministic start (poster_0, poster_1...)
        bg_gen = InfiniteScrollBackground(bg_images, phase_duration, self.bg_scroll_speed, self.bg_grid_cols, self.config)
        bg_clip = bg_gen.generate_clip()
        
        # Movie Overlay (Common)
        movie_clip = self._resize_to_width(movie_clip, self.config.width)
        # Center vertically relative to screen height
        movie_y = (self.config.height - movie_clip.size[1]) // 2
        movie_clip = movie_clip.set_position(('center', movie_y))
        
        return bg_clip, movie_clip, phase_duration

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _safe_load_video_clip(self, path: str, has_mask: bool = False, audio: bool = True) -> VideoFileClip:
        """Global Safe Video Loader: Handles corruption, audio issues, and integrity checks."""
        try:
            return load_video_clip(path, has_mask=has_mask, audio=audio)
        except BaseException as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            logger.error(f"❌ Failed to load video {Path(path).name}: {e}")
            raise

    def _load_overlay_clip(self, path: str) -> VideoFileClip:
        """Robust overlay loading: Handles MOV (alpha) vs MP4 (chroma key) & strips audio. Verifies integrity."""
        try:
            ext = Path(path).suffix.lower()
            
            # 1. Load Clip (No Audio)
            # MOV usually has alpha channel
            has_mask = (ext == '.mov')
            
            # Use Global Safe Loader (audio=False always for overlays)
            if ext == '.mp4':
                clip = load_video_clip(
                    path,
                    has_mask=has_mask,
                    audio=False,
                    force_remux=True,
                    allow_transcode=True,
                )
            else:
                clip = self._safe_load_video_clip(path, has_mask=has_mask, audio=False)
            
            # 2. Apply Chroma Key for MP4s (or if mask is missing)
            if ext != '.mov':
                # Assume black background for MP4 overlays
                # Check directly if mask is missing or force it
                try:
                    clip = clip.fx(vfx.mask_color, color=[0,0,0], thr=40, s=10)
                except Exception as e:
                    logger.warning(f"Chroma key failed for {Path(path).name}: {e}")
                
            # Probe after FX to ensure clip is decodable in render path
            try:
                clip.get_frame(0)
            except Exception as e:
                raise ValueError(f"Overlay clip failed after FX: {Path(path).name}. error={e}")
            return clip
        except Exception as e:
            logger.error(f"Failed to load overlay {Path(path).name}: {e}")
            raise

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
        # Add +50 pixels to push slightly below screen edge to prevent "floating"
        final_y = self.config.height - avatar_clip.size[1] + 50
        
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
        img_clip = img_clip.resize(height=int(self.config.hd_icon_height * 0.7))
        
        movie_width = movie_clip.size[0]
        movie_left_x = (self.config.width - movie_width) // 2
        pos_x = movie_left_x + movie_width - img_clip.size[0] - (self.config.hd_icon_padding * 2)
        pos_y = self.config.searchbox_phase_b_y + (self.config.hd_icon_padding * 2)
        
        return img_clip.set_position((pos_x, pos_y)).set_opacity(self.config.hd_icon_opacity)

    def _generate_overlay_events(self, total_duration: float, phase: str = 'B', layout_info: Optional[Dict] = None) -> List[VideoFileClip]:
        events = []
        current_time = 0.25
        
        if not self.assets['overlays']: return events
        
        event_count = 0
        while current_time < total_duration - 2.0:
            event_count += 1
            overlay_path = safe_random_choice(self.assets['overlays'])
            if not overlay_path: break
            
            ext = Path(overlay_path).suffix.lower()
            
            if ext in ['.mp4', '.mov']:
                # Use Robust Loading
                overlay_clip = self._load_overlay_clip(overlay_path)
                
                self.clips_to_close.append(overlay_clip)
                overlay_duration = min(overlay_clip.duration, total_duration - current_time)
                overlay_duration = self._safe_clip_duration(overlay_clip, overlay_duration)
                if overlay_duration <= 0:
                    continue
                
                # Chroma key is already applied in _load_overlay_clip
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
                finger_path = safe_random_choice(self.assets['png_finger'])
                if finger_path:
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
            clip = self._safe_load_video_clip(path)
            # Mute audio for End Card? Usually yes or no? 
            # Existing code didn't mute.
            # But we should check audio.
            # safe_load returns clip with audio if available.
            self.clips_to_close.append(clip)
            duration = clip.duration
        else:
            clip = ImageClip(path).set_duration(default_duration)
            duration = default_duration
        return clip.resize(newsize=(self.config.width, self.config.height)), duration

    def _safe_clip_duration(self, clip: VideoFileClip, desired: float) -> float:
        """Clamp duration to avoid reading beyond the last frame."""
        fps = clip.fps or 30
        epsilon = 1.0 / max(fps, 30)
        max_dur = max(0.0, clip.duration - epsilon)
        return max(0.0, min(desired, max_dur))

    def _prepare_bgm(self, total_duration: float, loop_music: bool = True, volume: float = 0.4) -> Optional[AudioFileClip]:
        if not self.assets['music']: return None
        music_path = safe_random_choice(self.assets['music'])
        if not music_path: return None
        
        logger.info(f"🎵 Preparing BGM: {Path(music_path).name}")
        
        bgm_clip = AudioFileClip(music_path)
        self.clips_to_close.append(bgm_clip)
        
        if loop_music and bgm_clip.duration < total_duration:
            bgm_clip = afx.audio_loop(bgm_clip, duration=total_duration)
        else:
            bgm_clip = bgm_clip.subclip(0, min(bgm_clip.duration, total_duration))
            
        return bgm_clip.volumex(volume)

    def _resize_to_width(self, clip: VideoFileClip, target_width: int) -> VideoFileClip:
        if clip.size[0] == target_width: return clip
        return clip.resize(target_width / clip.size[0])

    def _save_thumbnail(self, clip: CompositeVideoClip, video_path: str, seek_time: float = 0.1) -> Optional[str]:
        thumb_path = str(Path(video_path).with_suffix('.jpg'))
        try:
            target_time = seek_time
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

    def generate_phase_b_feb2026_logic(self, movie_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        """Feb 2026 Logic for Phase B"""
        logger.info("\n🎬 Generating Phase B (Feb 2026)...")
        # 1. Prepare Movie Clip
        has_mask = movie_path.endswith('.mov')
        movie_clip = self._safe_load_video_clip(movie_path, has_mask=has_mask)
        self.clips_to_close.append(movie_clip)
        
        phase_duration = movie_clip.duration
        
        layers = []
        screen_w, screen_h = self.config.width, self.config.height
        
        # 2. Global Background (Seamless)
        bg_gen = InfiniteScrollBackground(
            self.current_bg_images, 
            phase_duration, 
            self.config.bg_scroll_speed, 
            self.current_bg_cols, 
            self.config,
            start_time=bg_start_time
        )
        bg_clip = bg_gen.generate_clip()
        layers.append(bg_clip)
        
        # 3. Movie Group (Searchbox + Movie + HD + AdText)
        # Searchbox (Top, Full Width)
        sb_h = 0
        if self.assets['png_searchbox']:
             path = safe_random_choice(self.assets['png_searchbox'])
             if path:
                 sb_clip = ImageClip(path).set_duration(phase_duration)
                 sb_clip = self._resize_to_width(sb_clip, screen_w)
                 sb_clip = sb_clip.set_position(('center', 0))
                 layers.append(sb_clip)
                 sb_h = sb_clip.size[1]
                 
        # Movie (Top-Middle, below Searchbox)
        movie_clip = self._resize_to_width(movie_clip, screen_w)
        movie_y = sb_h # Directly below searchbox
        movie_clip = movie_clip.set_position(('center', movie_y))
        layers.append(movie_clip)
        
        # Define standard variables for relative positioning
        movie_w, movie_h = movie_clip.size
        movie_x = (screen_w - movie_w) // 2
        
        # HD Icon (Movie Top-Right with padding)
        if self.assets['png_hd']:
            hd_path = safe_random_choice(self.assets['png_hd'])
            if hd_path:
                hd_clip = ImageClip(hd_path).set_duration(phase_duration)
                # Resize smaller for logo-like feel
                hd_clip = hd_clip.resize(height=36)
                # Position: inside movie area with extra padding
                hd_x = movie_x + movie_w - hd_clip.size[0] - 40
                hd_y = movie_y + 20
                hd_clip = hd_clip.set_position((hd_x, hd_y))
                layers.append(hd_clip)

        # AdText (Below Movie)
        adtext_y = None
        adtext_h = 0
        if self.assets['png_adtext']:
            ad_path = safe_random_choice(self.assets['png_adtext'])
            if ad_path:
                ad_clip = ImageClip(ad_path).set_duration(phase_duration)
                ad_clip = self._resize_to_width(ad_clip, int(screen_w * 0.8))
                
                ad_y = movie_y + movie_clip.size[1] + 20
                ad_clip = ad_clip.set_position(('center', ad_y))
                layers.append(ad_clip)
                adtext_y = ad_y
                adtext_h = ad_clip.size[1]

        # 3.1/3.2 duplicated in older logic - removed to avoid double overlays

        # 4. Floating Layer (Centered Overlay)
        if self.assets['overlays']:
            cta_path = safe_random_choice(self.assets['overlays'])
            if cta_path:
                cta_clip = self._load_overlay_clip(cta_path)
                cta_start_time = 3.0
                desired_duration = phase_duration - cta_start_time
                safe_duration = self._safe_clip_duration(cta_clip, desired_duration)
                if safe_duration <= 0:
                    return CompositeVideoClip(layers, size=(screen_w, screen_h)), phase_duration
                if cta_clip.duration < safe_duration:
                    cta_clip = vfx.loop(cta_clip, duration=safe_duration)
                else:
                    cta_clip = cta_clip.subclip(0, safe_duration)
                self.clips_to_close.append(cta_clip)
                
                # Resize 0.6x - 0.7x
                scale = random.uniform(0.6, 0.7)
                new_cta_w = int(screen_w * scale)
                if new_cta_w % 2 != 0:
                    new_cta_w -= 1
                cta_clip = cta_clip.resize(width=new_cta_w)
                
                # Center on Screen
                cta_x = (screen_w - cta_clip.size[0]) // 2
                cta_y = (screen_h - cta_clip.size[1]) // 2
                
                # Transparency 50-60%
                cta_clip = cta_clip.set_opacity(random.uniform(0.5, 0.6))
                
                # Start Time: 3.0s
                cta_clip = cta_clip.set_start(cta_start_time).set_position((cta_x, cta_y))
                layers.append(cta_clip)
                
                # Small Searchbox (Inside Overlay, Bottom Middle)
                if self.assets['png_searchbox']:
                    small_sb_path = safe_random_choice(self.assets['png_searchbox'])
                    if small_sb_path:
                        if safe_duration > 0:
                            small_sb = ImageClip(small_sb_path).set_duration(safe_duration)
                            small_sb = small_sb.set_start(cta_start_time)
                            
                            # Width = 3/4 of Overlay
                            target_w = int(cta_clip.size[0] * 0.75)
                            small_sb = self._resize_to_width(small_sb, target_w)
                            
                            # Center inside Overlay
                            ssb_x = cta_x + (cta_clip.size[0] - target_w) // 2
                            ssb_y = cta_y + (cta_clip.size[1] - small_sb.size[1]) // 2
                            
                            small_sb = small_sb.set_position((ssb_x, ssb_y))
                            layers.append(small_sb)
                            
                            # Finger (Below Small Searchbox)
                            if self.assets['png_finger']:
                                f_path = safe_random_choice(self.assets['png_finger'])
                                if f_path:
                                    finger_img = ImageClip(f_path).set_duration(safe_duration)
                                    finger_img = finger_img.set_start(cta_start_time)
                                    
                                    # Width = 3/4 of Overlay (match searchbox)
                                    finger_img = self._resize_to_width(finger_img, target_w)
                                    
                                    # Position: Below Small Searchbox
                                    f_x = ssb_x + (small_sb.size[0] - finger_img.size[0]) // 2 + 50
                                    f_y = ssb_y + small_sb.size[1] + 10
                                    
                                    # Keep finger below AdText on screen when possible
                                    if adtext_y is not None and adtext_h > 0:
                                        adtext_bottom = adtext_y + adtext_h
                                        min_below = adtext_bottom + 8
                                        min_visible = adtext_y + int(adtext_h * 0.3)
                                        f_y = max(f_y, min_below)
                                        max_f_y = screen_h - finger_img.size[1]
                                        if f_y > max_f_y:
                                            f_y = max(min_visible, max_f_y)
                                    
                                    # Clamp to screen
                                    f_y = max(0, min(f_y, screen_h - finger_img.size[1]))
                                    
                                    # Animation: Floating/Pulse
                                    finger_img = finger_img.resize(lambda t: 1.0 + 0.1 * (math.sin(t*5)**2))
                                    finger_img = finger_img.set_position((f_x, f_y))
                                    layers.append(finger_img)

                                 
        phase_clip = CompositeVideoClip(layers, size=(screen_w, screen_h))
        if movie_clip.audio:
            phase_clip = phase_clip.set_audio(movie_clip.audio)
        return phase_clip, phase_duration

# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

class VideoTemplate:
    """Abstract Strategy for Video Patterns"""
    def __init__(self, generator: 'DualPhaseGenerator'):
        self.gen = generator
        self.config = generator.config
        self.assets = generator.assets


    def create_phase_a(self, avatar_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        raise NotImplementedError

    def create_phase_b(self, movie_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        raise NotImplementedError

class Dec2025Template(VideoTemplate):
    """Classic December 2025 Layout"""
    
    def create_phase_a(self, avatar_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        # Copied from original generate_phase_a (Dec 2025 branch)
        return self.gen.generate_phase_a_legacy_logic(avatar_path)

    def create_phase_b(self, movie_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        # Copied from original generate_phase_b (Dec 2025 branch)
        return self.gen.generate_phase_b_legacy_logic(movie_path)

class Feb2026Template(VideoTemplate):
    """New February 2026 Layout"""
    
    def create_opening_sequence(self, bg_start_time: float = 0.0) -> Optional[CompositeVideoClip]:
        # Robust Resource Management
        if not self.assets.get('png_free'): return None
        
        try:
            # 1. Select ONE image and ONE Audio
            img_path = random.choice(self.assets['png_free'])
            audio_path = None
            
            if self.assets.get('audio_free'):
                try:
                    audio_path = random.choice(self.assets['audio_free'])
                except Exception as e:
                    logger.warning(f"Failed to select audio: {e}")

            # 2. Calculate Strict Timing (Audio repeats, Video x2)
            # Plus: Speed up opening 2-3x (video only, keep audio pitch natural).
            video_repeats = 2
            
            # Prepare Audio Track
            final_audio = None
            base_audio = None
            base_audio_dur = 0.0
            # Speed-up factor (2x-3x)
            speed_factor = random.uniform(2.0, 3.0)
            min_loop_after_speed = 0.6  # ensure 2nd loop is perceptible
            min_total_before_speed = min_loop_after_speed * video_repeats * speed_factor
            if audio_path:
                base_audio = AudioFileClip(audio_path)
                self.gen.clips_to_close.append(base_audio)
                base_audio_dur = base_audio.duration or 0.0
                # Repeat audio as needed to cover minimum visible duration
                audio_repeats = 3
                if base_audio_dur > 0:
                    need_repeats = math.ceil(min_total_before_speed / base_audio_dur)
                    audio_repeats = max(audio_repeats, need_repeats)
                    final_audio = concatenate_audioclips([base_audio] * audio_repeats)
                    base_total_duration = final_audio.duration
                else:
                    base_total_duration = max(1.5, min_total_before_speed)
            else:
                base_total_duration = max(1.5, min_total_before_speed)
            if base_total_duration <= 0:
                base_total_duration = 0.8
                
            # Calculate Video Clip Duration
            # The 2 video loops must fit exactly into total_duration
            single_video_duration = base_total_duration / video_repeats
            
            video_clips = []
            cumulative_time = bg_start_time
            
            for _ in range(video_repeats):
                # Global Background (Seamless)
                bg_gen = InfiniteScrollBackground(
                    self.gen.current_bg_images, 
                    single_video_duration, 
                    self.gen.config.bg_scroll_speed, 
                    self.gen.current_bg_cols, 
                    self.gen.config,
                    start_time=cumulative_time
                )
                bg_clip = bg_gen.generate_clip()
                
                # Opening Image (Aspect Fit + Padding)
                img_clip = ImageClip(img_path).set_duration(single_video_duration)
                
                # Resize to fit within 80% of screen width/height (20% padding)
                max_w = int(self.gen.config.width * 0.8)
                max_h = int(self.gen.config.height * 0.8)
                img_clip = img_clip.resize(width=max_w)
                if img_clip.size[1] > max_h:
                    img_clip = img_clip.resize(height=max_h)
                    
                # Center
                canvas_w, canvas_h = self.gen.config.width, self.gen.config.height
                new_w, new_h = img_clip.size
                
                # Animation (Random Zoom/Slide)
                anim_type = random.choice(['zoom_in', 'zoom_out', 'slide_left', 'slide_right', 'pulse'])
                
                if anim_type == 'zoom_in':
                    img_clip = img_clip.resize(lambda t: 1 + 0.1 * (t/single_video_duration))
                elif anim_type == 'zoom_out':
                    img_clip = img_clip.resize(lambda t: 1.1 - 0.1 * (t/single_video_duration))
                elif anim_type == 'slide_left':
                    img_clip = img_clip.set_position(lambda t: (int((canvas_w - new_w)//2 - 50 * (t/single_video_duration)), 'center'))
                elif anim_type == 'slide_right':
                    img_clip = img_clip.set_position(lambda t: (int((canvas_w - new_w)//2 + 50 * (t/single_video_duration)), 'center'))
                elif anim_type == 'pulse':
                     img_clip = img_clip.resize(lambda t: 1 + 0.05 * (math.sin(t*5)**2))

                # Default Position if not animated by slide
                if 'slide' not in anim_type:
                    img_clip = img_clip.set_position('center')
                
                # Composite
                comp_clip = CompositeVideoClip([bg_clip, img_clip], size=(canvas_w, canvas_h))
                video_clips.append(comp_clip)
                cumulative_time += single_video_duration
                
            final_clip = concatenate_videoclips(video_clips)
            # Speed up video only to keep audio pitch natural
            final_clip = final_clip.fx(vfx.speedx, speed_factor)
            if final_audio:
                target_dur = final_clip.duration
                if target_dur and target_dur > 0:
                    if not final_audio.duration or final_audio.duration <= 0:
                        final_audio = None
                    elif final_audio.duration < target_dur:
                        final_audio = afx.audio_loop(final_audio, duration=target_dur)
                    else:
                        final_audio = final_audio.subclip(0, target_dur)
                if final_audio:
                    final_clip = final_clip.set_audio(final_audio)
            
            return final_clip
            
        except Exception as e:
            logger.exception(f"Opening sequence error: {e}")
            return None
    
        


    def create_phase_a(self, avatar_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        # Implement Feb 2026 logic using self.gen helpers
        # Re-using the logic extracted from generate_phase_a
        return self.gen.generate_phase_a_feb2026_logic(avatar_path, bg_start_time)

    def create_phase_b(self, movie_path: str, bg_start_time: float = 0.0) -> Tuple[CompositeVideoClip, float]:
        # Implement Feb 2026 logic using self.gen helpers
        return self.gen.generate_phase_b_feb2026_logic(movie_path, bg_start_time)

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
