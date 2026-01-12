from src.video_engine import VideoEngine
from src import config
import os
import pandas as pd
from src import utils

def test_generation():
    print("Starting Ghost Layer Video Verification...")
    
    # Needs to find assets effectively or mock pool
    pool = utils.get_files_with_extensions(config.OVERLAY_DIR, ['.mp4', '.mov'])
    print(f"Overlay Pool: {pool}")
    
    row = {
        'id': 777,
        'avatar': os.path.join(config.AVATAR_DIR, "avatar1.mp4"),
        'movie': os.path.join(config.MOVIE_DIR, "movie1.mp4"),
        'end_card': os.path.join(config.END_CARD_DIR, "end1.mp4"),
        'overlay': pool[0] if pool else None, # Primary
        'background': None # Let's test fallback or poster logic if assets exist
    }
    
    output_path = os.path.join(config.OUTPUT_DIR, "test_ghost_video.mp4")
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        
    engine = VideoEngine()
    success = engine.create_video(row, output_path, overlay_pool=pool)
    
    if success:
        print(f"SUCCESS: Video generated at {output_path}")
    else:
        print("FAILURE: Video generation failed.")

if __name__ == "__main__":
    test_generation()
