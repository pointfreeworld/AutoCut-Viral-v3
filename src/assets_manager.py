# -*- coding: utf-8 -*-
import random
from typing import Dict, List

from src import config
from src import utils
from src.assets import scan_assets

logger = utils.setup_logger()

class AssetManager:
    def __init__(self):
        self.avatars: List[str] = []
        self.movies: List[str] = []
        self.end_cards: List[str] = []
        self.overlays: List[str] = []
        self.stickers: List[str] = []
        self.backgrounds: List[str] = []
        self.refresh_assets()

    def refresh_assets(self):
        """
        扫描目录并加载资源 (Scan directories and load assets)
        """
        assets = scan_assets(config.ASSETS_DIR)
        self.avatars = assets.get('avatars', [])
        self.movies = assets.get('movies', [])
        self.end_cards = assets.get('end_cards', [])
        self.overlays = assets.get('overlays', [])
        self.stickers = assets.get('stickers', [])
        self.backgrounds = assets.get('backgrounds', [])
        
        logger.info(f"Loaded assets: {len(self.avatars)} Avatars, {len(self.movies)} Movies, {len(self.end_cards)} End Cards, {len(self.overlays)} Overlays, {len(self.stickers)} Stickers, {len(self.backgrounds)} Backgrounds")

    def get_batch_plan(self, count=1):
        """
        生成批量生成计划 (Generate batch generation plan)
        返回 DataFrame 用于追踪
        """
        import pandas as pd

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
                'background': random.choice(self.backgrounds) if self.backgrounds else None,
                'sticker': random.choice(self.stickers) if self.stickers else None
            }
            plans.append(plan)
        
        return pd.DataFrame(plans)
