# -*- coding: utf-8 -*-
import os

# 路径配置 (Path Configurations)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

AVATAR_DIR = os.path.join(ASSETS_DIR, "avatars")
MOVIE_DIR = os.path.join(ASSETS_DIR, "movies")
END_CARD_DIR = os.path.join(ASSETS_DIR, "end_cards")
OVERLAY_DIR = os.path.join(ASSETS_DIR, "overlays")
STICKER_DIR = os.path.join(ASSETS_DIR, "stickers")
BACKGROUND_DIR = os.path.join(ASSETS_DIR, "0_backgrounds")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 视频参数 (Video Parameters)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# 默认时长配置 (Default Durations)
AVATAR_DURATION = 5  # seconds
# MOVIE_DURATION will be dynamic
END_CARD_DURATION = 3 # seconds
# TOTAL_DURATION will be dynamic (40-60s)

# Ghost Layer 配置 (Ghost Layer Config)
GHOST_START_TIME = 0.25 # seconds
GHOST_INTERVAL = 5.0 # seconds (repeat every 5 seconds)
GHOST_DURATION = 1.0 # seconds (display duration)
GHOST_OPACITY = 0.4 # 40% opacity

# 编码配置 (Encoding Config)
CODEC = 'libx264'
PRESET = 'ultrafast'
THREADS = 4
BITRATE = '5000k'
