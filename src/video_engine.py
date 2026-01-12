# -*- coding: utf-8 -*-
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx, ColorClip
import os
import random
import numpy as np
from src import config
from src import utils

from src.poster_wall import PosterWallGenerator

logger = utils.setup_logger()

class VideoEngine:
    def __init__(self):
        self.poster_wall_gen = PosterWallGenerator()

    def create_video(self, plan_row, output_filename, overlay_pool=None, sticker_pool=None, progress_callback=None):
        """
        根据计划的一行生成单个视频 (Generate a single video based on a plan row)
        progress_callback: function(int) -> updates progress bar 0-100
        """
        clips_to_close = []
        try:
            if progress_callback: progress_callback(10, "Loading Assets...")

            # 1. 加载资源 (Load Assets)
            avatar_path = plan_row['avatar']
            movie_path = plan_row['movie']
            end_card_path = plan_row['end_card']
            
            # Avatar Settings
            avatar_scale = plan_row.get('avatar_scale', 1.0)
            avatar_pos_x = plan_row.get('avatar_pos_x', 0)
            avatar_pos_y = plan_row.get('avatar_pos_y', 0)

            # Pools
            current_overlay_pool = overlay_pool if overlay_pool else []
            if not current_overlay_pool and plan_row.get('overlay'):
                 current_overlay_pool = [plan_row['overlay']]
            
            current_sticker_pool = sticker_pool if sticker_pool else []

            background_path = plan_row.get('background')
            
            # Background Settings
            bg_shuffle = plan_row.get('bg_shuffle', True)
            bg_columns = plan_row.get('bg_columns', 3)
            bg_speed = plan_row.get('bg_speed', 500)

            logger.info(f"Processing: {output_filename}")

            if progress_callback: progress_callback(30, "Processing Avatar & Green Screen...")
            
            # 2. 处理 Avatar Intro (Process Avatar)
            # FIX 1: .mov Check & Tuned Masking
            if avatar_path.endswith('.mov'):
                # Assume has alpha
                avatar_clip = VideoFileClip(avatar_path, has_mask=True)
            else:
                avatar_clip = VideoFileClip(avatar_path)
                # FIX 1b: Tuned mp4 masking thr=140
                try:
                    avatar_clip = avatar_clip.fx(vfx.mask_color, color=[0, 255, 0], thr=140, s=10)
                except Exception as e:
                    logger.warning(f"Failed to apply green screen mask to avatar: {e}")
            
            clips_to_close.append(avatar_clip)

            # FEATURE: Avatar UI Customization (Scale, Pos)
            # Base Resize (Width)
            base_width = config.VIDEO_WIDTH
            if avatar_scale != 1.0:
                base_width = int(config.VIDEO_WIDTH * avatar_scale)
            
            avatar_clip = self._resize_to_width(avatar_clip, base_width)
            
            # Position Logic
            # ('center', 'bottom') -> Center X + offset_x, Bottom - offset_y
            center_x = (config.VIDEO_WIDTH - avatar_clip.w) // 2
            final_x = center_x + int(avatar_pos_x)
            final_y = config.VIDEO_HEIGHT - avatar_clip.h - int(avatar_pos_y) # Calculate from top for 'bottom' offset
            
            # Use tuple for specific position (integers)
            avatar_clip = avatar_clip.set_position((int(final_x), int(final_y)))
            
            avatar_duration = avatar_clip.duration
            
            # 3. 处理 End Card (Process End Card)
            if end_card_path.endswith(('.png', '.jpg')):
                end_card_clip = ImageClip(end_card_path).set_duration(config.END_CARD_DURATION)
            else:
                end_card_clip = VideoFileClip(end_card_path)
                clips_to_close.append(end_card_clip)
                if end_card_clip.duration > config.END_CARD_DURATION:
                    end_card_clip = end_card_clip.subclip(0, config.END_CARD_DURATION)
            
            end_card_clip = self._resize_to_width(end_card_clip, config.VIDEO_WIDTH)
            end_card_clip = end_card_clip.set_position("center")

            # 4. Determine Dynamic Duration
            target_movie_duration = random.randint(30, 45) 
            actual_total_duration = avatar_duration + target_movie_duration + end_card_clip.duration
            logger.info(f"Dynamic Plan: Intro={avatar_duration:.1f}s, Movie={target_movie_duration}s, End={end_card_clip.duration}s. Total={actual_total_duration:.1f}s")

            if progress_callback: progress_callback(50, "Processing Movie Highlights...")

            # 5. 处理 Movie Highlights (Process Movie Splicing)
            movie_main_clip = VideoFileClip(movie_path)
            clips_to_close.append(movie_main_clip)
            
            movie_spliced_clip, splice_log = self._process_movie_clips(movie_main_clip, target_movie_duration)
            movie_spliced_clip = self._resize_to_width(movie_spliced_clip, config.VIDEO_WIDTH)
            
            # Position: Top Half (y=250)
            movie_spliced_clip = movie_spliced_clip.set_position(("center", 250))
            
            # Add Black Bars
            top_bar = ColorClip(size=(config.VIDEO_WIDTH, 50), color=(0,0,0)).set_duration(movie_spliced_clip.duration).set_position(('center', 'top'))
            bottom_bar = ColorClip(size=(config.VIDEO_WIDTH, 50), color=(0,0,0)).set_duration(movie_spliced_clip.duration).set_position(('center', 'bottom'))
            
            # Movie Composite
            movie_block = CompositeVideoClip(
                [movie_spliced_clip, top_bar, bottom_bar], 
                size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
            ).set_duration(movie_spliced_clip.duration)

            if progress_callback: progress_callback(60, "Stitching Poster Wall...")
            
            # Layers Assembly (Composite Approach)
            layers = []
            
            # Layer 0: Background
            bg_images = utils.get_files_with_extensions(config.BACKGROUND_DIR, ['.png', '.jpg', '.jpeg'])
            if bg_images:
                bg_clip = self.poster_wall_gen.generate_scroll_clip(
                    bg_images, 
                    duration=actual_total_duration,
                    columns=bg_columns,
                    speed=bg_speed,
                    shuffle=bg_shuffle
                )
                if bg_clip:
                    clips_to_close.append(bg_clip) 
                    layers.append(bg_clip)
                else:
                    layers.append(self._get_fallback_bg(actual_total_duration))
            elif background_path and os.path.exists(background_path):
                bg_clip = VideoFileClip(background_path)
                clips_to_close.append(bg_clip)
                if bg_clip.duration < actual_total_duration:
                    bg_clip = bg_clip.fx(vfx.loop, duration=actual_total_duration)
                else:
                    bg_clip = bg_clip.subclip(0, actual_total_duration)
                bg_clip = self._resize_to_fill(bg_clip, config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
                layers.append(bg_clip)
            else:
                 layers.append(self._get_fallback_bg(actual_total_duration))

            if progress_callback: progress_callback(70, "Composing Layers...")

            # Calculate Start Times for Segments
            t_avatar_start = 0
            t_movie_start = avatar_duration
            t_end_start = avatar_duration + target_movie_duration
            
            # FIX 2: Z-Index Reordering
            # Order: [Bg, Movie, Ghost_CTA, Avatar, Decorations]
            
            # 1. Movie Layer (Starts at t_movie_start)
            layers.append(movie_block.set_start(t_movie_start))
            
            # 2. Ghost CTA (Throughout)
            if current_overlay_pool:
                overlay_clip = self._create_ghost_layer(current_overlay_pool, actual_total_duration)
                if overlay_clip:
                    layers.append(overlay_clip)
            
            # 3. Avatar Layer (Starts at 0) - ON TOP of Ghost
            layers.append(avatar_clip.set_start(t_avatar_start))
            
            # 4. End Card (Starts at t_end_start) - Usually Covers everything
            layers.append(end_card_clip.set_start(t_end_start))
            
            # 5. Decorations - Top Most
            if current_sticker_pool:
                decoration_clip = self._create_decoration_layer(current_sticker_pool, actual_total_duration)
                if decoration_clip:
                    layers.append(decoration_clip)

            if progress_callback: progress_callback(90, "Rendering Final Video...")
            
            # Composite
            final_clip = CompositeVideoClip(layers, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).set_duration(actual_total_duration)

            # 8. 导出 (Export)
            write_audio = final_clip.audio is not None

            final_clip.write_videofile(
                output_filename,
                codec=config.CODEC,
                preset=config.PRESET,
                threads=config.THREADS,
                fps=config.FPS,
                audio_codec='aac' if write_audio else None,
                audio=write_audio,
                logger=None 
            )
            
            if progress_callback: progress_callback(100, "Done!")
            logger.info(f"Generated: {output_filename}")
            return True

        except Exception as e:
            logger.error(f"Error generating video {output_filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            for clip in clips_to_close:
                try:
                    clip.close()
                except:
                    pass
    
    def _get_fallback_bg(self, duration):
        from moviepy.editor import ColorClip
        return ColorClip(size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color=(0,0,0), duration=duration)

    def _process_movie_clips(self, source_clip, target_duration):
        clips = []
        current_dur = 0
        log_parts = []
        
        while current_dur < target_duration:
            remaining = target_duration - current_dur
            if remaining < 3:
                clip_dur = remaining
            else:
                clip_dur = random.uniform(3, 6)
                if remaining - clip_dur < 1:
                    clip_dur = remaining
            
            if source_clip.duration > clip_dur:
                start = random.uniform(0, source_clip.duration - clip_dur)
            else:
                start = 0
                clip_dur = source_clip.duration 
            
            sub = source_clip.subclip(start, start + clip_dur)
            clips.append(sub)
            log_parts.append(f"{clip_dur:.1f}s")
            current_dur += clip_dur
            
            if abs(current_dur - target_duration) < 0.1: 
                break
        
        if clips:
            final = concatenate_videoclips(clips)
        else:
            final = source_clip.subclip(0, target_duration) 
            
        return final, f"{len(clips)} clips ({', '.join(log_parts)})"

    def _resize_to_width(self, clip, target_width):
        w, h = clip.size
        # Handle cases where size might be odd
        ratio = target_width / w
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        # Ensure even dimensions for encoding
        if new_w % 2 != 0: new_w += 1
        if new_h % 2 != 0: new_h += 1
        return clip.resize((new_w, new_h))

    def _resize_to_fill(self, clip, target_w, target_h):
        w, h = clip.size
        ratio_w = target_w / w
        ratio_h = target_h / h
        ratio = max(ratio_w, ratio_h)
        new_size = (int(w * ratio), int(h * ratio))
        clip_resized = clip.resize(new_size)
        clip_cropped = clip_resized.crop(
            x_center=clip_resized.w / 2,
            y_center=clip_resized.h / 2,
            width=target_w,
            height=target_h
        )
        return clip_cropped

    def _create_ghost_layer(self, overlay_pool, total_duration):
        if not overlay_pool:
            return None

        ghost_clips = []
        current_time = 0.25 
        
        target_width = int(config.VIDEO_WIDTH * 0.5) 

        while current_time < total_duration:
            overlay_path = random.choice(overlay_pool)
            try: 
                if overlay_path.endswith(('.mp4', '.mov')):
                    clip = VideoFileClip(overlay_path)
                    if overlay_path.endswith('.mp4'):
                        try:
                            # Use mask_color 0 for black
                            clip = clip.fx(vfx.mask_color, color=[0,0,0], thr=10, s=10)
                        except Exception as e:
                            logger.warning(f"Could not apply mask color to {overlay_path}: {e}")
                else:
                    clip = ImageClip(overlay_path).set_duration(config.GHOST_DURATION)

                if clip.w != target_width:
                     clip = self._resize_to_width(clip, target_width)

                clip = clip.set_opacity(0.7)
                clip = clip.set_start(current_time)
                
                if current_time + clip.duration > total_duration:
                    clip = clip.subclip(0, total_duration - current_time)
                
                # Random Position in SAFE ZONE
                safe_margin = 200
                max_x = config.VIDEO_WIDTH - clip.w
                max_y = config.VIDEO_HEIGHT - clip.h - safe_margin
                min_y = safe_margin
                
                pos_x = random.randint(0, max(0, max_x))
                pos_y = random.randint(min_y, max(min_y, max_y))
                
                clip = clip.set_position((pos_x, pos_y))
                ghost_clips.append(clip)
                
                gap = random.uniform(2.0, 3.0)
                current_time += clip.duration + gap
                
            except Exception as e:
                logger.error(f"Failed to process ghost overlay {overlay_path}: {e}")
                current_time += 1.0

        if not ghost_clips:
            return None
        return CompositeVideoClip(ghost_clips, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).set_duration(total_duration)

    def _create_decoration_layer(self, sticker_pool, total_duration):
        if not sticker_pool:
            return None
            
        sticker_clips = []
        num_stickers = random.randint(3, 6) 
        
        for _ in range(num_stickers):
            try:
                sticker_path = random.choice(sticker_pool)
                img = ImageClip(sticker_path)
                dur = random.uniform(2.0, 5.0)
                w = random.randint(100, 300)
                img = self._resize_to_width(img, w)
                
                start_t = random.uniform(0, total_duration - dur)
                img = img.set_start(start_t).set_duration(dur)
                
                pos_x = random.randint(0, config.VIDEO_WIDTH - w)
                pos_y = random.randint(0, config.VIDEO_HEIGHT - int(w * img.h / img.w))
                
                img = img.set_position((pos_x, pos_y))
                sticker_clips.append(img)
            except Exception as e:
                pass
                
        if not sticker_clips:
            return None
        return CompositeVideoClip(sticker_clips, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).set_duration(total_duration)
