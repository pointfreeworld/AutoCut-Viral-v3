# -*- coding: utf-8 -*-
"""
AutoCut-Viral: Production-Ready Streamlit UI
6-Phase Workflow with Smart Resume and Output Gallery
"""

import streamlit as st
import logging
import os
import re
from pathlib import Path
from datetime import datetime
import random
from PIL import Image, ImageOps
from dual_phase_generator import DualPhaseGenerator, AssetScanner, setup_logging
from src.media_io import configure_ffmpeg

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AutoCut-Viral Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)
configure_ffmpeg()
setup_logging()
app_logger = logging.getLogger("App")

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def save_uploaded_files(uploaded_files, target_dir):
    """Save uploaded files to target directory"""
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    saved_count = 0
    for uploaded_file in uploaded_files:
        file_path = target_path / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_count += 1
    
    return saved_count

def scan_existing_videos(output_dir, date_str):
    """
    Scan output directory for existing videos matching today's date
    Returns: (max_id, existing_files)
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return 0, []
    mmdd = date_str[4:] if len(date_str) == 8 else date_str
    pattern = re.compile(rf"^(?:.*-)?{mmdd}-(\d+)(?:-[A-Za-z0-9]+)?\.mp4$")
    existing_files = []
    max_id = 0
    for file in output_path.rglob("*.mp4"):
        match = pattern.match(file.name)
        if match:
            video_id = int(match.group(1))
            max_id = max(max_id, video_id)
            existing_files.append(str(file))
    return max_id, existing_files

def get_gallery_items(output_dir, _refresh_trigger=None):
    """
    Get all video/thumbnail pairs for gallery display.
    _refresh_trigger parameter forces cache invalidation when changed.
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return []
    
    items = []
    for video_file in sorted(output_path.rglob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        thumb_file = video_file.with_suffix('.jpg')
        items.append({
            'video': str(video_file),
            'thumb': str(thumb_file) if thumb_file.exists() else None,
            'name': video_file.name
        })
    
    return items

def make_square_preview(image_path, size=300):
    """
    Create a square preview of an image with black letterboxing.
    Does NOT save to disk - returns PIL Image object for display only.
    
    Args:
        image_path: Path to original thumbnail
        size: Target square size in pixels
        
    Returns:
        PIL.Image object (square with black letterboxing)
    """
    try:
        img = Image.open(image_path)
        # Pad to square with black background
        square_img = ImageOps.pad(img, (size, size), color='black', centering=(0.5, 0.5))
        return square_img
    except Exception as e:
        # Return None if image processing fails
        return None

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def init_session_state():
    """Initialize session state variables"""
    defaults = {
        # Phase 0: Backgrounds - FIXED RANGES v3.0
        'bg_grid_cols': (3, 5),
        'bg_scroll_speed': (700, 1200),  # Fixed range 700-1200
        'shuffle_posters': True,  # NEW - Randomize poster order
        
        # Phase 1: Digital Human - v1.0: Sweet spot default 0.78
        'avatar_scale': (0.6, 0.8),  # Range 0.1-1.0, default 0.6-0.8
        'avatar_stroke': 5,
        'avatar_x_offset': (-100, 100),
        
        # Phase 3: End Card - now mandatory
        
        # Phase 4: Music - FIXED RANGES v3.0
        'bgm_volume': 0.2,  # Fixed range 0.1-1.2, default 0.2
        'loop_music': True,
        
        # Generation
        'batch_size': 1,
        'output_dir': 'output',
        'assets_scanned': False,
        'stop_requested': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR: ASSET STATUS
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📊 Asset Status")
    
    if st.button("🔄 Refresh Assets", width="stretch"):
        st.session_state.assets_scanned = False
        st.rerun()
        
    # Check history
    import json
    history_count = 0
    if Path("history.json").exists():
        try:
            with open("history.json") as f:
                history_count = len(json.load(f))
        except: pass
        
    st.metric("History Pairs", history_count)
    if st.button("🗑️ Clear History", width="stretch"):
        if Path("history.json").exists():
            Path("history.json").unlink()
            st.toast("History Cleared!")
            st.rerun()
    
    # Scan assets
    if not st.session_state.assets_scanned:
        with st.spinner("Scanning assets..."):
            # Robustness: Base path relative to app.py location
            base_assets_path = Path(__file__).parent.resolve() / "assets"
            scanner = AssetScanner(base_path=base_assets_path)
            st.session_state.assets = scanner.scan_all()
            st.session_state.assets_scanned = True
    
    assets = st.session_state.assets
    
    # Complete asset status with all types including End Cards
    st.metric("Backgrounds", len(assets['backgrounds']))
    st.metric("Avatars", len(assets['avatars']))
    st.metric("Movies", len(assets['movies']))
    st.metric("Overlays", len(assets['overlays']))
    st.metric("Music Tracks", len(assets['music']))
    st.metric("End Cards", len(assets.get('end_cards', [])))
    
    st.divider()
    st.caption("PNG Assets")
    st.metric("App List (Left)", len(assets.get('png_applist', [])))
    st.metric("Text List (Right)", len(assets.get('png_textlist', [])))
    st.metric("Ad Text", len(assets.get('png_adtext', [])))
    st.metric("Search Box", len(assets.get('png_searchbox', [])))
    st.metric("Finger", len(assets.get('png_finger', [])))
    st.metric("HD Icon", len(assets.get('png_hd', [])))
    
    st.divider()
    st.caption("Free Assets (Feb 2026)")
    st.metric("Free Images", len(assets.get('png_free', [])))
    st.metric("Free Audio", len(assets.get('audio_free', [])))
    
    st.divider()
    
    # Check required assets
    required_ok = all([
        assets['backgrounds'],
        assets['avatars'],
        assets['movies']
    ])
    
    if required_ok:
        st.success("✅ Required assets ready")
    else:
        st.error("❌ Missing required assets")
        if not assets['backgrounds']:
            st.warning("Upload backgrounds in Phase 0")
        if not assets['avatars']:
            st.warning("Upload avatars in Phase 1")
        if not assets['movies']:
            st.warning("Upload movies in Phase 2")



# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATES & UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════

def render_template_ui(template_id, template_name, default_config=None):
    """
    Render the complete UI for a specific template.
    All widgets are namespaced with `template_id` to ensure independent state.
    """
    
    # Helper for namespaced keys
    def k(key): return f"{template_id}_{key}"
    
    # Initialize defaults for this template if not present
    if k('bg_grid_cols') not in st.session_state:
        st.session_state[k('bg_grid_cols')] = default_config.get('bg_grid_cols', (3, 5))
        st.session_state[k('bg_scroll_speed')] = default_config.get('bg_scroll_speed', (700, 1200))
        st.session_state[k('shuffle_posters')] = default_config.get('shuffle_posters', True)
        st.session_state[k('avatar_scale')] = default_config.get('avatar_scale', (0.6, 0.8))
        st.session_state[k('avatar_stroke')] = default_config.get('avatar_stroke', 5)
        st.session_state[k('avatar_x_offset')] = default_config.get('avatar_x_offset', (-100, 100))
        st.session_state[k('bgm_volume')] = default_config.get('bgm_volume', 0.2)
        st.session_state[k('loop_music')] = default_config.get('loop_music', True)
        st.session_state[k('batch_size')] = default_config.get('batch_size', 1)
        st.session_state[k('machine_tag')] = default_config.get('machine_tag', os.getenv("ACV_MACHINE_TAG", "A"))

    st.markdown(f"### 🛠️ Configuration: {template_name}")
    
    # ─── PHASE 0: POSTER BACKGROUNDS ───
    with st.expander("📂 **Phase 0: Poster Backgrounds**", expanded=False):
        uploaded_bg = st.file_uploader(
            "Upload Background Images",
            type=['jpg', 'jpeg', 'png', 'webp'],
            accept_multiple_files=True,
            key=k("upload_bg")
        )
        
        if uploaded_bg:
            if st.button("💾 Save Backgrounds", key=k("save_bg")):
                count = save_uploaded_files(uploaded_bg, "assets/0_backgrounds")
                st.success(f"✅ Saved {count} background(s)")
                st.session_state.assets_scanned = False
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.session_state[k('bg_grid_cols')] = st.slider(
                "Columns (min, max)", 2, 5, st.session_state[k('bg_grid_cols')], key=k("slider_bg_cols")
            )
        with col2:
            st.session_state[k('bg_scroll_speed')] = st.slider(
                "Speed (px/s)", 500, 1500, st.session_state[k('bg_scroll_speed')], key=k("slider_bg_speed")
            )
        st.session_state[k('shuffle_posters')] = st.checkbox(
            "🔀 Shuffle Posters", value=st.session_state[k('shuffle_posters')], key=k("check_shuffle_posters")
        )

    # ─── OPENING SEQUENCE (Feb 2026 Only) ───
    if template_id == "feb2026":
        with st.expander("🆓 **Opening Sequence (Free Assets)**", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                up_free_img = st.file_uploader(
                    "Free Images (PNG/JPG)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key=k("up_free_img")
                )
                if up_free_img and st.button("💾 Save Free Images", key=k("save_free_img")):
                    count = save_uploaded_files(up_free_img, "assets/png_free")
                    st.success(f"✅ {count} saved")
                    st.session_state.assets_scanned = False
            with c2:
                up_free_aud = st.file_uploader(
                    "Free Audio (MP3/WAV)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=True, key=k("up_free_aud")
                )
                if up_free_aud and st.button("💾 Save Free Audio", key=k("save_free_aud")):
                    count = save_uploaded_files(up_free_aud, "assets/audio_free")
                    st.success(f"✅ {count} saved")
                    st.session_state.assets_scanned = False

    # ─── PHASE 1: DIGITAL HUMAN ───
    with st.expander("🎭 **Phase 1: Digital Human**", expanded=False):
        uploaded_avatar = st.file_uploader(
            "Upload Avatars (MP4/MOV)", type=['mp4', 'mov'], accept_multiple_files=True, key=k("upload_avatar")
        )
        if uploaded_avatar:
            if st.button("💾 Save Avatars", key=k("save_avatar")):
                count = save_uploaded_files(uploaded_avatar, "assets/avatars")
                st.success(f"✅ Saved {count} avatar(s)")
                st.session_state.assets_scanned = False
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state[k('avatar_scale')] = st.slider(
                "Scale", 0.1, 1.0, st.session_state[k('avatar_scale')], 0.1, key=k("slider_avatar_scale")
            )
        with c2:
            st.session_state[k('avatar_stroke')] = st.slider(
                "Stroke (px)", 3, 10, st.session_state[k('avatar_stroke')], key=k("slider_avatar_stroke")
            )
        with c3:
            st.session_state[k('avatar_x_offset')] = st.slider(
                "X-Offset", -150, 150, st.session_state[k('avatar_x_offset')], key=k("slider_avatar_x")
            )
            
        st.divider()
        uploaded_ad_p1 = st.file_uploader(
            "Upload Ad Text (Phase A)", type=['png', 'jpg'], accept_multiple_files=True, key=k("upload_ad_p1")
        )
        if uploaded_ad_p1 and st.button("💾 Save Ad Text", key=k("save_ad_p1")):
            count = save_uploaded_files(uploaded_ad_p1, "assets/png_adtext")
            st.success(f"✅ {count} saved")
            st.session_state.assets_scanned = False

    # ─── PHASE 2: MOVIE CLIP ───
    with st.expander("🎥 **Phase 2: Movie Clip**", expanded=False):
        uploaded_movie = st.file_uploader(
            "Upload Movies (MP4/MOV)", type=['mp4', 'mov'], accept_multiple_files=True, key=k("upload_movie")
        )
        if uploaded_movie and st.button("💾 Save Movies", key=k("save_movie")):
            count = save_uploaded_files(uploaded_movie, "assets/movies")
            st.success(f"✅ {count} saved")
            st.session_state.assets_scanned = False
            
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            up_search = st.file_uploader("Search Box (PNG)", type=['png'], key=k("upload_search"))
            if up_search and st.button("💾 Save Search Box", key=k("save_search")):
                count = save_uploaded_files(up_search, "assets/png_searchbox")
                st.success(f"✅ {count} saved")
                st.session_state.assets_scanned = False
        with c2:
            up_hd = st.file_uploader("HD Icon (PNG)", type=['png'], key=k("upload_hd"))
            if up_hd and st.button("💾 Save HD Icon", key=k("save_hd")):
                count = save_uploaded_files(up_hd, "assets/png_hd")
                st.success(f"✅ {count} saved")
                st.session_state.assets_scanned = False

    # ─── PHASE 3 & 4: END CARD & MUSIC ───
    with st.expander("🎵 **Phase 3 & 4: End Card & Music**", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            up_end = st.file_uploader("End Cards", type=['png','mp4','jpg'], accept_multiple_files=True, key=k("up_end"))
            if up_end and st.button("💾 Save End Cards", key=k("save_end")):
                save_uploaded_files(up_end, "assets/end_cards")
                st.session_state.assets_scanned = False
        with c2:
            up_music = st.file_uploader("Music", type=['mp3','wav'], accept_multiple_files=True, key=k("up_music"))
            if up_music and st.button("💾 Save Music", key=k("save_music")):
                save_uploaded_files(up_music, "assets/music")
                st.session_state.assets_scanned = False
        
        st.divider()
        st.session_state[k('bgm_volume')] = st.slider("BGM Volume", 0.1, 1.2, st.session_state[k('bgm_volume')], 0.05, key=k("slider_bgm"))
        st.session_state[k('loop_music')] = st.checkbox("Loop Music", st.session_state[k('loop_music')], key=k("chk_loop"))

    # ─── PHASE 5: OVERLAYS ───
    with st.expander("🎨 **Phase 5: Overlays & Interaction**", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            up_over = st.file_uploader("Overlays", type=['png','mp4'], accept_multiple_files=True, key=k("up_over"))
            if up_over and st.button("💾 Save Overlays", key=k("save_over")):
                save_uploaded_files(up_over, "assets/overlays")
                st.session_state.assets_scanned = False
        with c2:
            up_fing = st.file_uploader("Finger Cursor", type=['png'], key=k("up_fing"))
            if up_fing and st.button("💾 Save Finger", key=k("save_fing")):
                save_uploaded_files(up_fing, "assets/png_finger")
                st.session_state.assets_scanned = False

    # ─── GENERATION ───
    st.divider()
    st.header(f"🚀 Generate: {template_name}")
    
    c_batch, c_info = st.columns([1, 3])
    with c_batch:
        st.session_state[k('batch_size')] = st.number_input(
            "Batch Size", 1, 500, st.session_state[k('batch_size')], key=k("in_batch")
        )
        st.session_state[k('machine_tag')] = st.text_input(
            "Machine Tag", st.session_state[k('machine_tag')], max_chars=8, key=k("in_tag")
        )
    
    with c_info:
        date_str = datetime.now().strftime("%Y%m%d")
        max_id, _ = scan_existing_videos(st.session_state.output_dir, date_str)
        start_id = max_id + 1
        st.info(f"📊 Will generate {st.session_state[k('batch_size')]} video(s) starting from ID: {start_id}")

    col_btn, col_stop = st.columns([3, 1])
    with col_btn:
        generate = st.button(f"🎬 Start Generation ({template_name})", type="primary", width="stretch", key=k("btn_gen"))
    with col_stop:
        if st.button("🛑 Stop", width="stretch", key=k("btn_stop")):
            st.session_state.stop_requested = True
            st.warning("Stop requested...")

    if generate:
        # Validate assets
        assets = st.session_state.assets
        if not all([assets['backgrounds'], assets['avatars'], assets['movies']]):
            st.error("❌ Missing required assets (Backgrounds, Avatars, or Movies)!")
            return

        output_dir = Path(st.session_state.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # UI Progress
        st.markdown("### ⏳ Progress")
        batch_bar = st.progress(0, text="Batch Starting...")
        render_bar = st.progress(0, text="Initializing...")
        status = st.empty()
        
        # Initialize Generator
        generator = DualPhaseGenerator(assets)
        st.session_state.stop_requested = False
        batch_size = st.session_state[k('batch_size')]
        
        generated = []
        for i in range(batch_size):
            if st.session_state.stop_requested:
                status.warning("🛑 Stopped by user!")
                break
                
            vid = start_id + i
            batch_bar.progress(i / batch_size, text=f"Processing {i+1}/{batch_size}")
            status.text(f"🎬 Generating Video {vid}...")
            
            try:
                # Get random parameters from RANGES
                scale_min, scale_max = st.session_state[k('avatar_scale')]
                speed_min, speed_max = st.session_state[k('bg_scroll_speed')]
                col_min, col_max = st.session_state[k('bg_grid_cols')]
                
                result = generator.generate(
                    output_path=output_dir / "temp.mp4",
                    video_id=vid,
                    date_str=date_str,
                    loop_music=st.session_state[k('loop_music')],
                    bgm_volume=st.session_state[k('bgm_volume')],
                    shuffle_backgrounds=st.session_state[k('shuffle_posters')],
                    st_progress_bar=render_bar,
                    st_status_text=status,
                    avatar_scale=random.uniform(scale_min, scale_max),
                    bg_scroll_speed=random.randint(speed_min, speed_max),
                    bg_grid_cols=random.randint(col_min, col_max),
                    avatar_x_offset=st.session_state[k('avatar_x_offset')],
                    machine_tag=st.session_state[k('machine_tag')],
                    template_id=template_id # explicit strategy selection
                )
                generated.append(result)
                batch_bar.progress((i + 1) / batch_size)
                
            except Exception as e:
                app_logger.exception("Generation failed")
                st.error(f"❌ Error: {str(e)}")
                break
        
        status.success(f"✅ Completed! Generated {len(generated)} videos.")
        st.balloons()
        
        # Trigger Gallery Refresh
        import time
        st.session_state.gallery_refresh_ts = time.time()
        time.sleep(1)
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# MAIN HEADER
# ═══════════════════════════════════════════════════════════════════════════

st.title("🎬 AutoCut-Viral Generator")
st.markdown("**Production-Ready Edition** • Multi-Template Support")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATES TABS
# ═══════════════════════════════════════════════════════════════════════════

# Initialize global state if needed
if 'assets_scanned' not in st.session_state:
    st.session_state.assets_scanned = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'output_dir' not in st.session_state:
    st.session_state.output_dir = 'output'

# Default Configs (Can be different per template)
DEFAULT_CONFIG = {
    'bg_grid_cols': (3, 5),
    'bg_scroll_speed': (700, 1200),
    'avatar_scale': (0.6, 0.8),
    'avatar_stroke': 5,
}

tab_feb26, tab_dec25 = st.tabs(["🔥 Feb 2026", "❄️ Dec 2025"])

with tab_feb26:
    st.caption("Newest Template - February 2026 Edition")
    render_template_ui("feb2026", "Feb 2026 Template", DEFAULT_CONFIG)

with tab_dec25:
    st.caption("Classic Template - December 2025 Edition")
    render_template_ui("dec2025", "Dec 2025 Template", DEFAULT_CONFIG)


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT GALLERY
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.header("🖼️ Output Gallery")

# Use refresh trigger to ensure gallery updates after generation
refresh_ts = st.session_state.get('gallery_refresh_ts', 0)
gallery_items = get_gallery_items(st.session_state.output_dir, _refresh_trigger=refresh_ts)

if not gallery_items:
    st.info("📭 No videos generated yet. Generate some videos to see them here!")
else:
    st.caption(f"Showing {len(gallery_items)} video(s) • Google Drive-style grid")
    
    # Google Drive-style 6-column high-density grid
    cols_per_row = 6
    
    for i in range(0, len(gallery_items), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(gallery_items):
                item = gallery_items[idx]
                
                with col:
                    # Display square thumbnail (letterboxed) or placeholder
                    if item['thumb'] and Path(item['thumb']).exists():
                        square_preview = make_square_preview(item['thumb'], size=300)
                        if square_preview:
                            st.image(square_preview, width="stretch")
                        else:
                            st.info("📹")
                    else:
                        st.info("📹")
                    
                    # HEAD-truncation to show date/ID at end
                    filename = item['name']
                    if len(filename) > 25:
                        display_name = "..." + filename[-22:]  # Shows "...20260112-17.mp4"
                    else:
                        display_name = filename
                    st.caption(display_name, help=filename)
                    
                    # Dual download buttons with unique keys
                    btn_col1, btn_col2 = st.columns(2)
                    
                    with btn_col1:
                        if Path(item['video']).exists():
                            with open(item['video'], 'rb') as f:
                                st.download_button(
                                    "📹",
                                    data=f,
                                    file_name=filename,
                                    mime="video/mp4",
                                    key=f"dl_v_{idx}",
                                    width="stretch",
                                    help="Download MP4"
                                )
                    
                    with btn_col2:
                        if item['thumb'] and Path(item['thumb']).exists():
                            with open(item['thumb'], 'rb') as f:
                                st.download_button(
                                    "🖼️",
                                    data=f,
                                    file_name=Path(item['thumb']).name,
                                    mime="image/jpeg",
                                    key=f"dl_t_{idx}",
                                    width="stretch",
                                    help="Download JPG"
                                )

# ═══════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.caption("🎬 AutoCut-Viral Generator • Production-Ready Edition • Smart Resume Enabled")
