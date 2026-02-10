# -*- coding: utf-8 -*-
"""Media IO utilities.

Single source of truth for video loading and basic repair.
Goals:
- Force a known ffmpeg binary (imageio-ffmpeg)
- Read first frame to validate
- Auto-remux on failure, then retry
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List

from moviepy.editor import VideoFileClip
from moviepy.config import change_settings, get_setting
from imageio_ffmpeg import get_ffmpeg_exe

logger = logging.getLogger("MediaIO")


def configure_ffmpeg() -> str:
    """Force MoviePy to use imageio-ffmpeg binary.

    Returns the resolved ffmpeg path.
    """
    try:
        ffmpeg_path = get_ffmpeg_exe()
    except Exception:
        ffmpeg_path = get_setting("FFMPEG_BINARY") or "ffmpeg"
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        ffmpeg_path = "ffmpeg"
    change_settings({"FFMPEG_BINARY": ffmpeg_path})
    return ffmpeg_path


def _hash_path(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def _remux_video(src: str, dst: str, ffmpeg_path: str) -> Tuple[bool, str]:
    """Remux with ffmpeg (stream copy). Returns (ok, stderr).

    We keep this minimal: no re-encode, just rebuild container.
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-v",
        "error",
        "-i",
        src,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        dst,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    return ok, (proc.stderr or "").strip()

def _transcode_video(src: str, dst: str, ffmpeg_path: str) -> Tuple[bool, str]:
    """Transcode to a stable H.264 MP4 (yuv420p, CFR) for robustness."""
    cmd = [
        ffmpeg_path,
        "-y",
        "-v",
        "error",
        "-i",
        src,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-r",
        "30",
        dst,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    return ok, (proc.stderr or "").strip()

def _transcode_to_cache(path: str, cache_dir: Path, ffmpeg_path: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    trans_path = cache_dir / f"{Path(path).stem}-{_hash_path(path)}-x264.mp4"
    if trans_path.exists() and trans_path.stat().st_size > 0:
        return trans_path
    ok, stderr = _transcode_video(path, str(trans_path), ffmpeg_path)
    if not ok:
        raise ValueError(
            f"Failed to transcode: {Path(path).name}. ffmpeg_error={stderr[:600]}"
        )
    return trans_path
def _remux_to_cache(path: str, cache_dir: Path, ffmpeg_path: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    remux_path = cache_dir / f"{Path(path).stem}-{_hash_path(path)}.mp4"
    if remux_path.exists() and remux_path.stat().st_size > 0:
        return remux_path
    ok, stderr = _remux_video(path, str(remux_path), ffmpeg_path)
    if not ok:
        raise ValueError(
            f"Failed to remux: {Path(path).name}. ffmpeg_error={stderr[:600]}"
        )
    return remux_path


def _probe_frame(clip: VideoFileClip, times: List[float]) -> None:
    """Try to read a frame at multiple timestamps."""
    duration = clip.duration or 0.0
    last_error: Optional[Exception] = None
    for t in times:
        t_clamped = max(0.0, min(t, max(0.0, duration - 0.01)))
        try:
            clip.get_frame(t_clamped)
            return
        except Exception as e:
            last_error = e
            continue
    if last_error:
        raise last_error


def load_video_clip(
    path: str,
    *,
    has_mask: bool = False,
    audio: bool = True,
    repair_cache_dir: Optional[str] = None,
    read_test_time: float = 0.0,
    force_remux: bool = False,
    allow_transcode: bool = False,
) -> VideoFileClip:
    """Load a VideoFileClip with integrity check and auto-remux repair.

    Raises ValueError with a clear message on failure.
    """
    if not path or not os.path.exists(path):
        raise ValueError(f"File not found: {path}")
    if os.path.getsize(path) == 0:
        raise ValueError(f"Zero-byte file: {path}")

    ffmpeg_path = configure_ffmpeg()

    cache_dir = Path(repair_cache_dir) if repair_cache_dir else Path(path).parent / ".cache_remux"

    if force_remux:
        remux_path = _remux_to_cache(path, cache_dir, ffmpeg_path)
        try:
            clip = VideoFileClip(str(remux_path), has_mask=has_mask, audio=audio)
            probe_times = [read_test_time, 0.1, 0.0]
            _probe_frame(clip, probe_times)
            return clip
        except Exception:
            if not allow_transcode:
                raise
            trans_path = _transcode_to_cache(path, cache_dir, ffmpeg_path)
            clip = VideoFileClip(str(trans_path), has_mask=has_mask, audio=audio)
            probe_times = [read_test_time, 0.1, 0.0]
            _probe_frame(clip, probe_times)
            return clip

    try:
        clip = VideoFileClip(path, has_mask=has_mask, audio=audio)
        # Integrity check with fallback timestamps
        probe_times = [read_test_time, 0.1, 0.0]
        _probe_frame(clip, probe_times)
        return clip
    except Exception as e:
        # Try remux once, then re-open
        logger.warning(f"Video load failed, attempting remux: {Path(path).name} ({e})")
        remux_path = _remux_to_cache(path, cache_dir, ffmpeg_path)
        try:
            clip = VideoFileClip(str(remux_path), has_mask=has_mask, audio=audio)
            probe_times = [read_test_time, 0.1, 0.0]
            _probe_frame(clip, probe_times)
            return clip
        except Exception as e2:
            if allow_transcode:
                trans_path = _transcode_to_cache(path, cache_dir, ffmpeg_path)
                clip = VideoFileClip(str(trans_path), has_mask=has_mask, audio=audio)
                probe_times = [read_test_time, 0.1, 0.0]
                _probe_frame(clip, probe_times)
                return clip
            raise ValueError(
                f"Failed to read video after remux: {Path(path).name}. error={e2}"
            )
