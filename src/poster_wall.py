# -*- coding: utf-8 -*-
import os
import random
import math
import PIL.Image
from PIL import Image, ImageOps, ImageDraw
import numpy as np
from moviepy.editor import VideoClip
from src import config
from src import utils

logger = utils.setup_logger()

class PosterWallGenerator:
    def __init__(self):
        pass

    def generate_scroll_clip(self, image_paths, duration, columns=3, speed=100, gap=20, shuffle=True):
        """
        Generates a scrolling video clip from a list of images.
        """
        if not image_paths:
            logger.warning("No images provided for Poster Wall.")
            return None

        # 1. Prepare Images
        working_paths = image_paths[:]
        if shuffle:
            random.shuffle(working_paths)
            
        # 2. Canvas Config
        total_width = config.VIDEO_WIDTH
        item_width = int((total_width - (columns + 1) * gap) / columns)
        item_height = int(item_width * 1.5) # 2:3 ratio
        
        logger.info(f"Poster Wall: {len(working_paths)} images, {columns} cols. Item Size: {item_width}x{item_height}")

        # 3. Process Images
        processed_imgs = []
        for p in working_paths:
            try:
                img = Image.open(p).convert("RGBA")
                img = ImageOps.fit(img, (item_width, item_height), method=Image.LANCZOS)
                img = self._add_corners(img, radius=20)
                processed_imgs.append(img)
            except Exception as e:
                logger.error(f"Failed to load poster {p}: {e}")

        if not processed_imgs:
            return None

        # 4. Canvas Calculation
        # Multiply duration by speed to get pixel distance covered
        # Add buffer for screen height + loop safety
        needed_height_pixels = int(speed * duration + config.VIDEO_HEIGHT * 2)
        
        rows_per_set = math.ceil(len(processed_imgs) / columns)
        set_height = rows_per_set * (item_height + gap) + gap
        
        sets_needed = math.ceil(needed_height_pixels / set_height)
        sets_needed = max(2, sets_needed)
        
        canvas_width = total_width
        canvas_height = int(set_height * sets_needed)
        
        # 5. Paint Canvas
        # Create huge black image
        canvas = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
        
        current_img_index = 0
        
        # Iterate y position for rows
        y_offset = gap
        total_rows = sets_needed * rows_per_set
        
        for r in range(total_rows):
            x_offset = gap
            for c in range(columns):
                # Get image (cyclic)
                img = processed_imgs[current_img_index % len(processed_imgs)]
                current_img_index += 1
                
                # Paste
                canvas.paste(img, (x_offset, int(y_offset)), img)
                x_offset += item_width + gap
            
            y_offset += item_height + gap

        # 6. Create VideoClip
        canvas_array = np.array(canvas)
        
        def make_frame(t):
            # Scroll downwards (view moves down the canvas)
            # t goes 0 -> duration
            y_pos = int(speed * t)
            
            # Simple clamp mechanism
            y1 = y_pos
            y2 = y1 + config.VIDEO_HEIGHT
            
            # If we run off the end (shouldn't with our math), loop back or clamp
            if y2 > canvas_height:
                y1 = 0
                y2 = config.VIDEO_HEIGHT
            
            # Crop
            return canvas_array[y1:y2, :, :]

        return VideoClip(make_frame=make_frame, duration=duration)

    def _add_corners(self, im, radius):
        mask = Image.new('L', im.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
        
        out = im.copy()
        out.putalpha(mask)
        return out
