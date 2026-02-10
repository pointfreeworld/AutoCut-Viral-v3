#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example Usage: Dual-Phase Video Generator
This script demonstrates different ways to use the dual-phase generator
"""

from pathlib import Path
import sys

# Import the main generator and config
from dual_phase_generator import DualPhaseGenerator, AssetScanner, VideoConfig, setup_logging
from src.media_io import configure_ffmpeg, load_video_clip

def example_basic():
    """Example 1: Basic usage with all defaults"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Generation")
    print("="*70)
    
    # Scan assets
    scanner = AssetScanner(base_path="assets")
    assets = scanner.scan_all()
    
    # Generate video
    generator = DualPhaseGenerator(assets)
    output = generator.generate(output_path="output/example_basic.mp4", 
                                bg_grid_cols=3, bg_scroll_speed=950)
    
    print(f"\n✅ Generated: {output['video_path']}")


def example_custom_config():
    """Example 2: Custom configuration using VideoConfig"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Custom Configuration")
    print("="*70)
    
    # Create custom configuration
    config = VideoConfig(
        bgm_volume=0.3,
        digital_human_size=0.8,
        bg_scroll_speed=500,
        stroke_width=8
    )
    
    print(f"  BGM Volume: {config.bgm_volume}")
    print(f"  Digital Human Size: {config.digital_human_size}")
    print(f"  BG Scroll Speed: {config.bg_scroll_speed}")
    print(f"  Stroke Width: {config.stroke_width}")
    
    # Scan and generate
    scanner = AssetScanner(base_path="assets")
    assets = scanner.scan_all()
    
    # Pass config to generator
    generator = DualPhaseGenerator(assets, config=config)
    output = generator.generate(output_path="output/example_custom.mp4")
    
    print(f"\n✅ Generated: {output['video_path']}")


def example_concatenate_with_endcard():
    """Example 3: Concatenate with end card"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Concatenate with End Card")
    print("="*70)
    
    from moviepy.editor import concatenate_videoclips
    
    # First generate dual-phase
    scanner = AssetScanner(base_path="assets")
    assets = scanner.scan_all()
    
    generator = DualPhaseGenerator(assets)
    result = generator.generate(output_path="output/dual_phase_temp.mp4", bg_grid_cols=3)
    dual_phase_path = result['video_path']
    
    # Check if end card exists
    end_card_dir = Path("assets/end_cards")
    if end_card_dir.exists():
        end_cards = list(end_card_dir.glob("*.mp4"))
        if end_cards:
            print(f"\n🔗 Found end card: {end_cards[0].name}")
            
            # Load clips
            dual_phase = load_video_clip(dual_phase_path)
            end_card = load_video_clip(str(end_cards[0]))
            
            # Concatenate
            final = concatenate_videoclips([dual_phase, end_card], method="compose")
            
            # Export
            final_path = "output/complete_with_endcard.mp4"
            final.write_videofile(final_path, fps=30, codec='libx264', audio_codec='aac')
            
            print(f"\n✅ Generated complete video: {final_path}")
            
            # Cleanup
            dual_phase.close()
            end_card.close()
            final.close()
        else:
            print("\n⚠️  No end card MP4 files found in assets/end_cards/")
    else:
        print("\n⚠️  No assets/end_cards/ directory found")


def example_batch_generation():
    """Example 4: Batch generation of multiple videos"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Batch Generation")
    print("="*70)
    
    num_videos = 3
    
    # Scan assets once
    scanner = AssetScanner(base_path="assets")
    assets = scanner.scan_all()
    
    print(f"\nGenerating {num_videos} videos...")
    
    for i in range(num_videos):
        print(f"\n--- Video {i+1}/{num_videos} ---")
        
        # Use seed for reproducibility if needed, or random
        generator = DualPhaseGenerator(assets, seed=i*100) 
        result = generator.generate(output_path=f"output/batch_video_{i+1:03d}.mp4",
                                    bg_grid_cols=3)
        
        print(f"✅ {i+1}. {result['video_path']}")
    
    print(f"\n✅ Batch generation complete! Generated {num_videos} videos.")


if __name__ == "__main__":
    # Initialize logging
    setup_logging()
    configure_ffmpeg()
    
    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)
    
    # Run examples
    print("\n" + "="*70)
    print("DUAL-PHASE VIDEO GENERATOR - USAGE EXAMPLES")
    print("="*70)
    
    print("\nAvailable examples:")
    print("  1. Basic generation (default settings)")
    print("  2. Custom configuration")
    print("  3. Concatenate with end card")
    print("  4. Batch generation (3 videos)")
    
    choice = input("\nSelect example (1-4) or press Enter for basic: ").strip()
    
    if choice == "2":
        example_custom_config()
    elif choice == "3":
        example_concatenate_with_endcard()
    elif choice == "4":
        example_batch_generation()
    else:
        example_basic()
    
    print("\n" + "="*70)
    print("DONE!")
    print("="*70)
