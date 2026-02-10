import os
import random
from PIL import Image, ImageDraw
import numpy as np
from moviepy.editor import AudioFileClip, AudioClip

# Paths - match app.py logic
# Adjusted for tools/ directory location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

DIRS_TO_CREATE = [
    os.path.join(ASSETS_DIR, "png_free"),
    os.path.join(ASSETS_DIR, "audio_free"),
    os.path.join(ASSETS_DIR, "overlays"),
    os.path.join(ASSETS_DIR, "png_searchbox"),
    os.path.join(ASSETS_DIR, "png_finger"),
    os.path.join(ASSETS_DIR, "png_applist"),
    os.path.join(ASSETS_DIR, "png_textlist"),
]

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created dir: {path}")

def create_dummy_image(path, color, size=(1080, 1920), text=""):
    img = Image.new('RGB', size, color)
    draw = ImageDraw.Draw(img)
    # Draw an X
    draw.line((0, 0, size[0], size[1]), fill="white", width=20)
    draw.line((0, size[1], size[0], 0), fill="white", width=20)
    if text:
        # Simple text drawing (might fail if font not found, skips)
        pass 
    img.save(path)
    print(f"Created image: {path}")

def make_sine_wave(t):
    return 0.5 * np.sin(440 * 2 * np.pi * t)

def create_dummy_audio(path, duration=2.0):
    # generate 440Hz sine wave
    audio = AudioClip(make_sine_wave, duration=duration)
    # write to file
    audio.write_audiofile(path, fps=44100, logger=None)
    print(f"Created video: {path}")

def main():
    for d in DIRS_TO_CREATE:
        create_directory(d)

    # Free Images (Opening)
    for i in range(3):
        create_dummy_image(
            os.path.join(ASSETS_DIR, "png_free", f"free_{i}.png"), 
            (random.randint(0,255), random.randint(0,255), 0),
            size=(1080, 1920)
        )

    # Free Audio (Opening)
    for i in range(2):
        create_dummy_audio(
            os.path.join(ASSETS_DIR, "audio_free", f"sound_{i}.mp3"),
            duration=1.5
        )

    # Searchbox
    create_dummy_image(os.path.join(ASSETS_DIR, "png_searchbox", "sb.png"), (50,50,50), size=(600, 100))
    
    # Finger
    create_dummy_image(os.path.join(ASSETS_DIR, "png_finger", "finger.png"), (255,200,200), size=(100, 100))

    # Overlays (Video)
    # We need at least one .mp4 overlay for the code to pick it up for CTA
    # Reuse create_dummy_assets logic or simplified
    from moviepy.editor import ColorClip
    c = ColorClip(size=(500, 800), color=(0,0,255), duration=2.0)
    c.write_videofile(os.path.join(ASSETS_DIR, "overlays", "cta_overlay.mp4"), fps=10, logger=None)

    # Applist
    create_dummy_image(os.path.join(ASSETS_DIR, "png_applist", "apps.png"), (100,100,100), size=(200, 600))

if __name__ == "__main__":
    main()
