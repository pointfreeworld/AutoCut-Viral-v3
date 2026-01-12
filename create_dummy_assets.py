from moviepy.editor import ColorClip
from PIL import Image, ImageDraw
import os
import random

# Paths
ASSETS_DIR = "assets"
AVATAR_DIR = os.path.join(ASSETS_DIR, "avatars")
MOVIE_DIR = os.path.join(ASSETS_DIR, "movies")
END_CARD_DIR = os.path.join(ASSETS_DIR, "end_cards")
OVERLAY_DIR = os.path.join(ASSETS_DIR, "overlays")
BACKGROUND_DIR = os.path.join(ASSETS_DIR, "0_backgrounds")

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def create_dummy_video(path, color, duration=5, size=(1080, 1920)):
    clip = ColorClip(size=size, color=color, duration=duration)
    # Using low fps for speed
    clip.fps = 24
    clip.write_videofile(path, codec='libx264', preset='ultrafast', logger=None)
    print(f"Created video: {path}")

def create_dummy_overlay_video(path, duration=3, size=(500, 200)):
    # Create black background (to test masking)
    clip = ColorClip(size=size, color=(0,0,0), duration=duration)
    # Ideally draw something white/colored in middle but ColorClip is plain
    # To test actual masking, we need non-black content.
    # MoviePy ColorClip is single color.
    # We can use TextClip? TextClip often requires ImageMagick.
    # Let's use Pillow to make a sequence of images and turn into video.
    
    frames = []
    fps = 10
    for i in range(int(duration * fps)):
        img = Image.new('RGB', size, (0, 0, 0)) # Black bg
        draw = ImageDraw.Draw(img)
        # Draw red circle moving
        x = int((i / (duration * fps)) * size[0])
        draw.ellipse([x, 50, x+50, 100], fill=(255, 0, 0)) # Red ball
        frames.append(img)
    
    from moviepy.editor import ImageSequenceClip
    # Convert PIL images to numpy arrays (ImageSequenceClip handles list of numpy arrays or paths)
    import numpy as np
    frames_np = [np.array(f) for f in frames]
    
    clip_seq = ImageSequenceClip(frames_np, fps=fps)
    clip_seq.write_videofile(path, codec='libx264', preset='ultrafast', logger=None)
    print(f"Created overlay video: {path}")

def create_dummy_image(path, color, size=(1080, 1920), text=""):
    img = Image.new('RGB', size, color)
    draw = ImageDraw.Draw(img)
    draw.line((0, 0, size[0], size[1]), fill="black", width=10)
    draw.line((0, size[1], size[0], 0), fill="black", width=10)
    img.save(path)
    print(f"Created image: {path}")

def main():
    create_directory(AVATAR_DIR)
    create_directory(MOVIE_DIR)
    create_directory(END_CARD_DIR)
    create_directory(OVERLAY_DIR)
    create_directory(BACKGROUND_DIR)

    # Avatar
    create_dummy_video(os.path.join(AVATAR_DIR, "avatar1.mp4"), (0, 255, 0), duration=5, size=(1080, 1920))
    
    # Movie
    create_dummy_video(os.path.join(MOVIE_DIR, "movie1.mp4"), (0, 0, 255), duration=60, size=(1920, 1080))
    
    # End Card
    create_dummy_video(os.path.join(END_CARD_DIR, "end1.mp4"), (255, 0, 0), duration=3, size=(1080, 1920))
    
    # Overlay Video (Black Background Red Ball)
    # Delete old png to avoid mix up in test
    png_path = os.path.join(OVERLAY_DIR, "overlay1.png")
    if os.path.exists(png_path):
        os.remove(png_path)
        
    create_dummy_overlay_video(os.path.join(OVERLAY_DIR, "overlay_vid1.mp4"), duration=3.0)
    create_dummy_overlay_video(os.path.join(OVERLAY_DIR, "overlay_vid2.mp4"), duration=2.0)
    
    # Background Posters
    for i in range(5):
        c = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        create_dummy_image(os.path.join(BACKGROUND_DIR, f"poster_{i}.jpg"), c, size=(400, 600))

if __name__ == "__main__":
    main()
