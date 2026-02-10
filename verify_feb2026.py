import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dual_phase_generator import DualPhaseGenerator
import logging
from src.media_io import configure_ffmpeg

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_feb2026():
    print("🚀 Starting Feb 2026 Template Verification...")
    configure_ffmpeg()
    
    assets_dir = Path(__file__).parent / "assets"
    
    # Initialize Generator
    # We rely on AssetScanner inside normally, but DualPhaseGenerator takes a dict
    # Let's use AssetScanner to populate it correctly
    from dual_phase_generator import AssetScanner
    
    scanner = AssetScanner(base_path=assets_dir)
    assets = scanner.scan_all()
    
    # Check if we have enough assets
    print(f"Assets found: { {k: len(v) for k,v in assets.items()} }")
    
    if not assets['avatars'] or not assets['movies']:
        print("❌ Missing avatars or movies! Run tools/create_dummy_assets.py first.")
        return False
        
    generator = DualPhaseGenerator(assets)
    
    # Output path
    output_dir = Path("output_test")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "verify_feb2026.mp4"
    
    # Cleanup previous
    if output_path.exists(): output_path.unlink()
    
    try:
        # Run Generation
        result = generator.generate(
            avatar_path_in=None, # Random
            movie_path_in=None, # Random
            output_path=str(output_path),
            video_id=999,
            template_id="feb2026", # <--- CRITICAL TEST
            loop_music=False
        )
        
        generated_path = Path(result['video_path'])
        print(f"✅ Generation Complete: {generated_path}")
        
        # Verify file exists and has size
        if generated_path.exists() and generated_path.stat().st_size > 1000:
            print("✅ Output file verified (Size > 1KB)")
            return True
        else:
            print(f"❌ Output file missing or empty: {generated_path}")
            return False
            
    except Exception as e:
        print(f"❌ Generation Failed with Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_feb2026()
    sys.exit(0 if success else 1)
