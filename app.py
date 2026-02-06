# -*- coding: utf-8 -*-
"""
AutoCut-Viral: Production-Ready Streamlit UI
6-Phase Workflow with Smart Resume and Output Gallery
"""

import streamlit as st
import os
import re
from pathlib import Path
from datetime import datetime
import random
from PIL import Image, ImageOps
from dual_phase_generator import DualPhaseGenerator, AssetScanner

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AutoCut-Viral Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    pattern = re.compile(rf".*-{mmdd}-(\d+)(?:-[A-Za-z0-9]+)?\.mp4$")
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
    
    # Scan assets
    if not st.session_state.assets_scanned:
        with st.spinner("Scanning assets..."):
            scanner = AssetScanner(base_path="assets")
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
# MAIN HEADER
# ═══════════════════════════════════════════════════════════════════════════

st.title("🎬 AutoCut-Viral Generator")
st.markdown("**Production-Ready Edition** • 6-Phase Workflow with Smart Resume")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 0: POSTER BACKGROUNDS
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("📂 **Phase 0: Poster Backgrounds**", expanded=False):
    st.markdown("Upload poster images for the scrolling background wall.")
    
    uploaded_bg = st.file_uploader(
        "Upload Background Images",
        type=['jpg', 'jpeg', 'png', 'webp'],
        accept_multiple_files=True,
        key="upload_bg"
    )
    
    if uploaded_bg:
        if st.button("💾 Save Backgrounds", key="save_bg"):
            count = save_uploaded_files(uploaded_bg, "assets/0_backgrounds")
            st.success(f"✅ Saved {count} background(s)")
            st.session_state.assets_scanned = False
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Grid Columns Range**")
        bg_cols = st.slider(
            "Columns (min, max)",
            min_value=2, max_value=5,
            value=st.session_state.bg_grid_cols,
            key="slider_bg_cols"
        )
        st.session_state.bg_grid_cols = bg_cols
    
    with col2:
        st.markdown("**Scroll Speed Range (px/s)**")
        bg_speed = st.slider(
            "Speed (min, max)",
            min_value=500, max_value=1500,
            value=st.session_state.bg_scroll_speed,
            key="slider_bg_speed"
        )
        st.session_state.bg_scroll_speed = bg_speed
    
    # Shuffle Posters checkbox
    shuffle_posters = st.checkbox(
        "🔀 Shuffle Posters",
        value=st.session_state.shuffle_posters,
        help="Randomize poster order for every video to ensure uniqueness",
        key="check_shuffle_posters"
    )
    st.session_state.shuffle_posters = shuffle_posters

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: DIGITAL HUMAN
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🎭 **Phase 1: Digital Human**", expanded=False):
    st.markdown("Configure digital human avatars with green screen removal.")
    
    uploaded_avatar = st.file_uploader(
        "Upload Avatar Videos (MP4/MOV)",
        type=['mp4', 'mov'],
        accept_multiple_files=True,
        key="upload_avatar"
    )
    
    if uploaded_avatar:
        if st.button("💾 Save Avatars", key="save_avatar"):
            count = save_uploaded_files(uploaded_avatar, "assets/avatars")
            st.success(f"✅ Saved {count} avatar(s)")
            st.session_state.assets_scanned = False
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Scale Range**")
        avatar_scale = st.slider(
            "Scale (min, max)",
            min_value=0.1, max_value=1.0,  # Wider range for smaller avatars
            value=st.session_state.avatar_scale,
            step=0.1,
            key="slider_avatar_scale"
        )
        st.session_state.avatar_scale = avatar_scale
    
    with col2:
        st.markdown("**White Stroke Width**")
        avatar_stroke = st.slider(
            "Stroke (px)",
            min_value=3, max_value=10,
            value=st.session_state.avatar_stroke,
            key="slider_avatar_stroke"
        )
        st.session_state.avatar_stroke = avatar_stroke
    
    with col3:
        st.markdown("**X-Offset Range**")  # Changed from Y-Offset to X-Offset
        avatar_x = st.slider(
            "X-Offset (min, max)",
            min_value=-150, max_value=150,  # Horizontal offset range
            value=st.session_state.avatar_x_offset,
            key="slider_avatar_x"
        )
        st.session_state.avatar_x_offset = avatar_x
    
    st.divider()
    st.markdown("**Shared: Ad Text Images**")
    
    uploaded_ad_p1 = st.file_uploader(
        "Upload Ad Text (PNG/JPG)",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key="upload_ad_p1"
    )
    
    if uploaded_ad_p1:
        if st.button("💾 Save Ad Text", key="save_ad_p1"):
            count = save_uploaded_files(uploaded_ad_p1, "assets/png_adtext")
            st.success(f"✅ Saved {count} ad text image(s)")
            st.session_state.assets_scanned = False

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: MOVIE CLIP
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🎥 **Phase 2: Movie Clip**", expanded=False):
    st.markdown("Upload movie content and search UI elements.")
    
    uploaded_movie = st.file_uploader(
        "Upload Movie Clips (MP4)",
        type=['mp4', 'mov'],
        accept_multiple_files=True,
        key="upload_movie"
    )
    
    if uploaded_movie:
        if st.button("💾 Save Movies", key="save_movie"):
            count = save_uploaded_files(uploaded_movie, "assets/movies")
            st.success(f"✅ Saved {count} movie(s)")
            st.session_state.assets_scanned = False
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Search Box**")
        uploaded_search = st.file_uploader(
            "Upload Search Box (PNG)",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True,
            key="upload_search"
        )
        
        if uploaded_search:
            if st.button("💾 Save Search Box", key="save_search"):
                count = save_uploaded_files(uploaded_search, "assets/png_searchbox")
                st.success(f"✅ Saved {count} search box(es)")
                st.session_state.assets_scanned = False
    
    with col2:
        st.markdown("**HD Icon**")
        uploaded_hd = st.file_uploader(
            "Upload HD Icon (PNG)",
            type=['png'],
            accept_multiple_files=True,
            key="upload_hd"
        )
        
        if uploaded_hd:
            if st.button("💾 Save HD Icon", key="save_hd"):
                count = save_uploaded_files(uploaded_hd, "assets/png_hd")
                st.success(f"✅ Saved {count} HD icon(s)")
                st.session_state.assets_scanned = False
    
    st.divider()
    st.markdown("**Shared: Ad Text Images**")
    st.caption("_Same folder as Phase 1 - uploading here will add to the same collection_")
    
    uploaded_ad_p2 = st.file_uploader(
        "Upload Ad Text (PNG/JPG)",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key="upload_ad_p2"  # Different key, same folder
    )
    
    if uploaded_ad_p2:
        if st.button("💾 Save Ad Text", key="save_ad_p2"):
            count = save_uploaded_files(uploaded_ad_p2, "assets/png_adtext")
            st.success(f"✅ Saved {count} ad text image(s)")
            st.session_state.assets_scanned = False

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: END CARD
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🎯 **Phase 3: End Card**", expanded=False):
    st.markdown("Upload end card images/videos for the finale.")
    
    uploaded_endcard = st.file_uploader(
        "Upload End Cards (PNG/MP4)",
        type=['png', 'jpg', 'jpeg', 'mp4'],
        accept_multiple_files=True,
        key="upload_endcard"
    )
    
    if uploaded_endcard:
        if st.button("💾 Save End Cards", key="save_endcard"):
            count = save_uploaded_files(uploaded_endcard, "assets/end_cards")
            st.success(f"✅ Saved {count} end card(s)")
            st.session_state.assets_scanned = False
    
    st.divider()
    
    # Removed checkbox - end card concatenation is now mandatory if assets exist
    if assets.get('end_cards'):
        st.info(f"ℹ️ End card will be automatically appended ({len(assets['end_cards'])} available)")
    else:
        st.warning("⚠️ No end cards uploaded - videos will end at movie clip phase")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: BACKGROUND MUSIC
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🎵 **Phase 4: Background Music**", expanded=False):
    st.markdown("Upload background music tracks.")
    
    uploaded_music = st.file_uploader(
        "Upload Music (MP3/WAV/M4A)",
        type=['mp3', 'wav', 'm4a'],
        accept_multiple_files=True,
        key="upload_music"
    )
    
    if uploaded_music:
        if st.button("💾 Save Music", key="save_music"):
            count = save_uploaded_files(uploaded_music, "assets/music")
            st.success(f"✅ Saved {count} music track(s)")
            st.session_state.assets_scanned = False
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        # Changed volume range to 0.1-1.2
        bgm_vol = st.slider(
            "BGM Volume",
            min_value=0.1, max_value=1.2,
            value=st.session_state.bgm_volume,
            step=0.05,
            key="slider_bgm_vol"
        )
        st.session_state.bgm_volume = bgm_vol
    
    with col2:
        # Added loop music checkbox
        loop_music = st.checkbox(
            "Loop Music",
            value=st.session_state.loop_music,
            key="check_loop_music",
            help="If unchecked, music will stop when track ends"
        )
        st.session_state.loop_music = loop_music

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: OVERLAYS & INTERACTION
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🎨 **Phase 5: Overlays & Interaction**", expanded=False):
    st.markdown("Upload interactive overlays (CTA buttons) and finger cursor.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**CTA Overlays**")
        uploaded_overlay = st.file_uploader(
            "Upload Overlays (MP4/PNG)",
            type=['mp4', 'mov', 'png'],
            accept_multiple_files=True,
            key="upload_overlay"
        )
        
        if uploaded_overlay:
            if st.button("💾 Save Overlays", key="save_overlay"):
                count = save_uploaded_files(uploaded_overlay, "assets/overlays")
                st.success(f"✅ Saved {count} overlay(s)")
                st.session_state.assets_scanned = False
    
    with col2:
        st.markdown("**Finger Cursor**")
        uploaded_finger = st.file_uploader(
            "Upload Finger (PNG)",
            type=['png'],
            accept_multiple_files=True,
            key="upload_finger"
        )
        
        if uploaded_finger:
            if st.button("💾 Save Finger", key="save_finger"):
                count = save_uploaded_files(uploaded_finger, "assets/png_finger")
                st.success(f"✅ Saved {count} finger image(s)")
                st.session_state.assets_scanned = False
    
    # Removed safe zone slider - backend calculates intelligently based on finger width

# ═══════════════════════════════════════════════════════════════════════════
# GENERATION SECTION
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.header("🚀 Video Generation")

col_batch, col_gen = st.columns([1, 3])

with col_batch:
    batch_size = st.number_input(
        "Batch Size",
        min_value=1, max_value=500,
        value=st.session_state.batch_size,
        key="input_batch_size"
    )
    st.session_state.batch_size = batch_size
    machine_tag_default = os.getenv("ACV_MACHINE_TAG", "A")
    machine_tag_val = st.text_input("机器标识符", value=machine_tag_default, max_chars=8, key="machine_tag_input")
    st.session_state.machine_tag = machine_tag_val

with col_gen:
    st.caption(f"Will generate {batch_size} video(s)")
    
    # Smart Resume Logic
    date_str = datetime.now().strftime("%Y%m%d")
    max_existing_id, existing_videos = scan_existing_videos(st.session_state.output_dir, date_str)
    
    if max_existing_id > 0:
        st.info(f"📊 Found {max_existing_id} existing video(s) from today. Will resume from #{max_existing_id + 1}")
        start_id = max_existing_id + 1
    else:
        start_id = 1

# Add Stop Button alongside Generate Button
col_gen_btn, col_stop_btn = st.columns([3, 1])

with col_gen_btn:
    generate_clicked = st.button("🎬 Generate Videos", type="primary", width="stretch")

with col_stop_btn:
    if st.button("🛑 Stop", width="stretch"):
        st.session_state.stop_requested = True
        st.warning("Stop requested - will halt after current video")

if generate_clicked:
    # Validate required assets
    if not all([assets['backgrounds'], assets['avatars'], assets['movies']]):
        st.error("❌ Missing required assets! Please upload backgrounds, avatars, and movies.")
    else:
        # Create output directory and a per-run timestamp subfolder
        Path(st.session_state.output_dir).mkdir(exist_ok=True)
        run_folder_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        run_folder = Path(st.session_state.output_dir) / run_folder_name
        run_folder.mkdir(parents=True, exist_ok=True)
        
        # Initialize DUAL progress tracking
        st.markdown("**📊 Progress**")
        batch_bar = st.progress(0, text="Batch Progress: 0%")
        render_bar = st.progress(0, text="Waiting to start...")
        status_text = st.empty()
        
        # Initialize generator
        generator = DualPhaseGenerator(assets)
        
        # Reset stop flag at start
        st.session_state.stop_requested = False
        
        # Generate videos
        generated_videos = []
        
        for i in range(batch_size):
            # Check stop flag
            if st.session_state.stop_requested:
                status_text.warning("🛑 Batch generation stopped by user!")
                st.warning(f"⚠️ Stopped at video {i+1}/{batch_size}. Generated {len(generated_videos)} video(s).")
                break
            
            video_id = start_id + i
            
            # Update status
            batch_progress = i / batch_size
            batch_bar.progress(batch_progress, text=f"Batch Progress: Video {i+1}/{batch_size}")
            render_bar.progress(0, text="Starting video generation...")
            status_text.text(f"🎬 Generating video {i+1}/{batch_size} (ID: {video_id:02d})...")
            
            # Select random assets
            avatar_path = random.choice(assets['avatars'])
            movie_path = random.choice(assets['movies'])
            
            try:
                # Get random scale from slider range
                scale_min, scale_max = st.session_state.avatar_scale
                avatar_scale_value = random.uniform(scale_min, scale_max)
                
                # Get random scroll speed and x_offset from slider ranges
                speed_min, speed_max = st.session_state.bg_scroll_speed
                bg_scroll_speed_value = random.randint(speed_min, speed_max)
                
                # Get random grid columns from slider range
                cols_min, cols_max = st.session_state.bg_grid_cols
                bg_grid_cols_value = random.randint(cols_min, cols_max)
                
                # Generate video with ALL UI settings passed to backend
                result = generator.generate(
                    avatar_path=avatar_path,
                    movie_path=movie_path,
                    output_path=run_folder / "temp.mp4",
                    video_id=video_id,
                    date_str=date_str,
                    loop_music=st.session_state.loop_music,
                    bgm_volume=st.session_state.bgm_volume,
                    shuffle_backgrounds=st.session_state.shuffle_posters,
                    st_progress_bar=render_bar,
                    st_status_text=status_text,
                    avatar_scale=avatar_scale_value,
                    bg_scroll_speed=bg_scroll_speed_value,
                    avatar_x_offset=st.session_state.avatar_x_offset,
                    bg_grid_cols=bg_grid_cols_value,
                    machine_tag=st.session_state.get("machine_tag", None)
                )
                
                generated_videos.append(result)
                
                # Update batch progress
                batch_progress = (i + 1) / batch_size
                batch_bar.progress(batch_progress, text=f"Batch Progress: {int(batch_progress * 100)}%")
                render_bar.progress(1.0, text="✅ Video complete!")
                
                # Update gallery refresh timestamp after each video
                import time
                st.session_state.gallery_refresh_ts = time.time()
                
            except Exception as e:
                import traceback
                traceback.print_exc()  # Print full traceback to terminal
                st.error(f"❌ Error generating video {video_id}: {str(e)}")
                break
        
        # Complete
        batch_bar.progress(1.0, text="Batch Complete! 🎉")
        render_bar.progress(1.0, text="All videos rendered!")
        status_text.success(f"✅ Generated {len(generated_videos)}/{batch_size} video(s)!")
        st.balloons()
        
        # Force gallery refresh by updating timestamp and triggering rerun
        import time
        st.session_state.gallery_refresh_ts = time.time()
        st.session_state.generation_just_completed = True
        
        # Short delay then force page rerun to refresh gallery
        time.sleep(1)
        st.rerun()

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
