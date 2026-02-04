# -*- coding: utf-8 -*-
import pandas as pd
import random
import os
from src import config
from src import utils

logger = utils.setup_logger()

class AssetManager:
    def __init__(self):
        self.avatars = []
        self.movies = []
        self.end_cards = []
        self.overlays = []
        self.backgrounds = []
        self.refresh_assets()

    def refresh_assets(self):
        """
        扫描目录并加载资源 (Scan directories and load assets)
        """
        self.avatars = utils.get_files_with_extensions(config.AVATAR_DIR, ['.mp4', '.mov'])
        self.movies = utils.get_files_with_extensions(config.MOVIE_DIR, ['.mp4', '.mov'])
        self.end_cards = utils.get_files_with_extensions(config.END_CARD_DIR, ['.mp4', '.mov', '.png', '.jpg'])
        self.overlays = utils.get_files_with_extensions(config.OVERLAY_DIR, ['.png', '.jpg', '.mp4', '.mov'])
        self.stickers = utils.get_files_with_extensions(config.STICKER_DIR, ['.png', '.jpg'])
        self.backgrounds = utils.get_files_with_extensions(config.BACKGROUND_DIR, ['.mp4', '.mov', '.png', '.jpg'])
        
        logger.info(f"Loaded assets: {len(self.avatars)} Avatars, {len(self.movies)} Movies, {len(self.end_cards)} End Cards, {len(self.overlays)} Overlays, {len(self.stickers)} Stickers, {len(self.backgrounds)} Backgrounds")

    def get_batch_plan(self, count=1):
        """
        生成批量生成计划 (Generate batch generation plan)
        返回 DataFrame 用于追踪
        """
        if not self.avatars or not self.movies or not self.end_cards:
            logger.error("Missing critical assets (Avatar, Movie, or End Card). Cannot generate plan.")
            return pd.DataFrame()

        plans = []
        for i in range(count):
            plan = {
                'id': i,
                'avatar': random.choice(self.avatars),
                'movie': random.choice(self.movies), # Will be used as source pool
                'end_card': random.choice(self.end_cards),
                'overlay': random.choice(self.overlays) if self.overlays else None,
                'background': random.choice(self.backgrounds) if self.backgrounds else None
            }
            plans.append(plan)
        
        return pd.DataFrame(plans)
