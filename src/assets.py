# -*- coding: utf-8 -*-
"""Asset scanning and validation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Union

logger = logging.getLogger("Assets")


@dataclass(frozen=True)
class AssetDirs:
    base_path: Path

    @property
    def backgrounds(self) -> Path:
        return self.base_path / "0_backgrounds"

    @property
    def avatars(self) -> Path:
        return self.base_path / "avatars"

    @property
    def movies(self) -> Path:
        return self.base_path / "movies"

    @property
    def overlays(self) -> Path:
        return self.base_path / "overlays"

    @property
    def stickers(self) -> Path:
        return self.base_path / "stickers"

    @property
    def music(self) -> Path:
        return self.base_path / "music"

    @property
    def end_cards(self) -> Path:
        return self.base_path / "end_cards"

    @property
    def png_applist(self) -> Path:
        return self.base_path / "png_applist"

    @property
    def png_textlist(self) -> Path:
        return self.base_path / "png_textlist"

    @property
    def png_adtext(self) -> Path:
        return self.base_path / "png_adtext"

    @property
    def png_searchbox(self) -> Path:
        return self.base_path / "png_searchbox"

    @property
    def png_finger(self) -> Path:
        return self.base_path / "png_finger"

    @property
    def png_hd(self) -> Path:
        return self.base_path / "png_hd"

    @property
    def png_free(self) -> Path:
        return self.base_path / "png_free"

    @property
    def audio_free(self) -> Path:
        return self.base_path / "audio_free"


def _scan_dir(path: Path, exts: List[str]) -> List[str]:
    if not path.exists():
        return []
    files = [str(p) for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return files


def scan_assets(base_path: Union[str, Path]) -> Dict[str, List[str]]:
    """Scan assets using a stable mapping.

    Returns a dict of asset lists keyed by logical type.
    """
    base = Path(base_path).resolve()
    dirs = AssetDirs(base)

    assets = {
        "backgrounds": _scan_dir(dirs.backgrounds, [".jpg", ".jpeg", ".png", ".webp"]),
        "avatars": _scan_dir(dirs.avatars, [".mp4", ".mov"]),
        "movies": _scan_dir(dirs.movies, [".mp4", ".mov"]),
        "overlays": _scan_dir(dirs.overlays, [".mp4", ".mov", ".png", ".jpg", ".jpeg"]),
        "stickers": _scan_dir(dirs.stickers, [".png", ".jpg", ".jpeg"]),
        "music": _scan_dir(dirs.music, [".mp3", ".wav", ".m4a"]),
        "end_cards": _scan_dir(dirs.end_cards, [".mp4", ".mov", ".png", ".jpg", ".jpeg"]),
        "png_applist": _scan_dir(dirs.png_applist, [".png", ".jpg", ".jpeg"]),
        "png_textlist": _scan_dir(dirs.png_textlist, [".png", ".jpg", ".jpeg"]),
        "png_adtext": _scan_dir(dirs.png_adtext, [".png", ".jpg", ".jpeg"]),
        "png_searchbox": _scan_dir(dirs.png_searchbox, [".png", ".jpg", ".jpeg"]),
        "png_finger": _scan_dir(dirs.png_finger, [".png"]),
        "png_hd": _scan_dir(dirs.png_hd, [".png"]),
        "png_free": _scan_dir(dirs.png_free, [".png", ".jpg", ".jpeg"]),
        "audio_free": _scan_dir(dirs.audio_free, [".mp3", ".wav", ".m4a"]),
    }

    logger.info(
        "Found assets: " + ", ".join([f"{k}={len(v)}" for k, v in assets.items()])
    )
    return assets
