from pathlib import Path
from moviepy.editor import VideoFileClip
from PIL import Image
import numpy as np
import os

def regenerate_thumbnails():
    output_dir = Path("output")
    if not output_dir.exists():
        print("Output directory not found.")
        return

    videos = list(output_dir.rglob("*.mp4"))
    print(f"Found {len(videos)} videos. Checking thumbnails...")

    for vid_path in videos:
        thumb_path = vid_path.with_suffix(".jpg")
        
        # Skip if temp file
        if vid_path.name.startswith(".tmp"):
            continue

        if not thumb_path.exists():
            print(f"Generating thumbnail for: {vid_path.name}")
            try:
                clip = VideoFileClip(str(vid_path))
                
                # Robust timestamp logic
                target_t = 0.1
                if clip.duration < 0.2:
                    target_t = 0.0
                
                frame = clip.get_frame(target_t)
                img = Image.fromarray(frame)
                img.save(thumb_path, "JPEG", quality=85)
                
                # Close clip to release handle
                clip.close()
                print(f"✅ Saved: {thumb_path.name}")
            except Exception as e:
                print(f"❌ Failed {vid_path.name}: {e}")
        else:
            print(f"⏭️  Exists: {thumb_path.name}")

if __name__ == "__main__":
    regenerate_thumbnails()
