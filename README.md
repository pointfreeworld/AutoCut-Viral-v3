# 🎬 AutoCut Viral
> **High-Performance Dual-Phase Video Generator for Viral Content Automation**

![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)
![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)

**AutoCut Viral** is a specialized video automation engine designed to create high-retention short-form content. It combines a **Digital Human Phase** (intro hook) with a **Movie Clip Phase** (retention), featuring dynamic overlays, anti-ban algorithms, and infinite scrolling backgrounds.

---

## ✨ Key Features

### 🎥 Dual-Phase Rendering
- **Phase A (Hook)**: Digital Human avatar with green screen removal (chroma key) and floating app/text panels.
- **Phase B (Retention)**: Movie clip highlight with dynamic search box, ad text, and HD icons.
- **Seamless Transition**: Pixel-perfect coordinate sharing between phases.

### 🛡️ Anti-Ban Architecture
- **Geometric Jitter**: Randomized Y offsets (±5-10px) for all UI elements to evade duplicate content detection.
- **Floating Animations**: Searchbox and panels use sine wave motion for organic feel.
- **Infinite Scroll**: Unique, non-repeating background patterns generated procedurally.
- **Atomic Writes**: `.tmp` file generation guarantees zero corrupted files even if process crashes.
- **Auto Cleanup**: `force_disk_cleanup()` runs on every startup, removing orphaned temp files.

### 🧩 Smart Layouts
- **Collision Avoidance**: Floating panels respect `avatar_safe_zone` (550px from bottom) to avoid overlapping the digital human.
- **Panel Width**: App List and Text List panels are sized to **1/3 screen width** (360px on 1080p).
- **Dynamic Overlays**: Randomized "Finger Tap" and reaction video overlays with intelligent spacing.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- FFmpeg（推荐；系统未安装时会使用 imageio-ffmpeg）
- ImageMagick（可选，用于高级文本效果）

---

### 🍎 macOS Installation

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install FFmpeg and ImageMagick
brew install ffmpeg imagemagick

# 3. Clone and setup
git clone https://github.com/pointfreeworld/AutoCut-Viral-v3.git
cd AutoCut-Viral-v3
pip3 install -r requirements.txt

# 4. Run
streamlit run app.py
```

---

### 🪟 Windows Installation

**Step 1: Install FFmpeg**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to System PATH

**Step 2: Install ImageMagick (Optional)**
1. Download from [imagemagick.org](https://imagemagick.org/script/download.php)
2. During install, check ✅ "Install legacy utilities (convert)"

**Step 3: Setup Project**
```powershell
# Clone repository
git clone https://github.com/pointfreeworld/AutoCut-Viral-v3.git
cd AutoCut-Viral-v3

# Install Python dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
```

---

### Usage

**1. Basic Generation (CLI)**
```bash
python3 example_usage.py
# Select Option 1 for default settings
```

**2. Streamlit UI (Web Interface)**
```bash
streamlit run app.py
```

---

## 📂 Asset Structure

Place your assets in the `assets/` directory. The system automatically scans these folders:

| Folder | Content | Supported Formats |
|--------|---------|-------------------|
| `avatars/` | Digital human videos (green screen preferred) | `.mp4`, `.mov` |
| `movies/` | Source movie clips for Phase B | `.mp4`, `.mov` |
| `0_backgrounds/` | Images for infinite scroll background | `.jpg`, `.png` |
| `png_applist/` | Left-side floating panels (1/3 screen width) | `.png` |
| `png_textlist/` | Right-side floating panels (1/3 screen width) | `.png` |
| `png_searchbox/` | Search bar images (with floating animation) | `.png` |
| `music/` | Background music tracks | `.mp3`, `.wav` |
| `png_adtext/` | Ad Text banners (pulsing animation) | `.png` |
| `png_finger/` | Finger tap interaction icons | `.png` |
| `png_hd/` | HD Quality Watermark icons | `.png` |
| `overlays/` | Reaction videos or dynamic stickers | `.mp4`, `.mov` |
| `stickers/` | 装饰贴纸 | `.png`, `.jpg` |
| `end_cards/` | Outro clips | `.mp4`, `.mov`, `.png`, `.jpg` |
| `png_free/` | 开场自由图片（Feb 2026 模板） | `.png`, `.jpg` |
| `audio_free/` | 开场自由音频（Feb 2026 模板） | `.mp3`, `.wav`, `.m4a` |

---

## 📝 Output Naming Convention

Generated videos follow a simplified naming format (machine tag optional):

```
MMDD-ID[-TAG].mp4
MMDD-ID[-TAG].jpg  (thumbnail)
```

**Examples:**
- `0210-01-A.mp4`
- `0210-02-A.jpg`
- `0210-03.mp4`  (no machine tag)

All outputs are written flat into the `output/` directory (no subfolders).

---

## ⚙️ Advanced Configuration (Headless Params)

Beyond the main parameters, `VideoConfig` controls strict anti-ban and layout preservation logic.

### 🛡️ Anti-Ban Logic

| Parameter | Value | Description |
|-----------|-------|-------------|
| `floating_panel_jitter` | ±5-10px | Random Y offset per generation |
| `searchbox_opacity_min/max` | 0.95-1.0 | Random opacity variation |
| `overlay_gap_min/max` | 2.0-3.0s | Random gaps between overlays |
| `searchbox_animation` | 5px @ 4s | Subtle floating motion |
| `floating_panel_animation` | 8px @ 3s | Sine wave motion |

### 📐 Layout Safe Zones

| Parameter | Value | Description |
|-----------|-------|-------------|
| `avatar_safe_zone` | 550px | Reserved height at bottom for avatar |
| `floating_panel_width` | 1/3 screen | 360px on 1080p resolution |
| `searchbox_phase_b_y` | 250px | Fixed Y position for searchbox |
| `finger_safe_zone` | Bottom 66% | Tap restricted to overlay lower area |

### 🔊 Audio Engineering

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bgm_volume` | 0.4x | Normalized to let voiceovers cut through |
| `loop_music` | Auto | Tracks shorter than video auto-loop |

### 🎞️ Motion Dynamics

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bg_scroll_speed` | 950 px/s | Infinite scroll speed |
| `adtext_pulse_scale` | 5% | Breathing effect amplitude |
| `adtext_pulse_frequency` | 1.5 Hz | Breathing effect speed |

---

## 🧹 Auto Cleanup

The system automatically cleans temp files on every startup:

```python
# Runs in __init__
def force_disk_cleanup():
    patterns = ['*.tmp', '.tmp_*', 'temp_*', '*.tmp.mp4']
    # Scans root and output directories
```

This ensures no orphaned files accumulate from crashed sessions.

---

## 🔧 Media IO 机制（重要）

为避免 “failed to read the first frame” 这类问题，项目统一使用 `src/media_io.py` 加载视频：

- 强制使用 imageio-ffmpeg（避免系统 ffmpeg 版本漂移）
- 首帧读取失败会自动进行 **remux 修复**（无重编码）
- 修复后会再次校验首帧，仍失败则抛出明确错误
- 修复缓存输出到 `assets/**/.cache_remux/`（按源文件生成）

---

## 🛠 Troubleshooting

**1. "ImageMagick not found" error**
MoviePy requires ImageMagick for TextClips.
- **Mac**: `brew install imagemagick`
- **Windows**: Download installer and check "Install legacy utilities (convert)".

**2. Thumbnails missing**
Thumbnails are generated at the end of the process. If a crash occurs, no thumbnail is created. Check `app.log` for errors.

**3. "AttributeError: 'NoneType' object has no attribute 'duration'"**
Ensure your `avatars/` and `movies/` folders are not empty. The generator requires at least one of each.

**4. Gallery not refreshing**
After generation completes, the page auto-refreshes. If videos are missing, manually refresh the browser.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
