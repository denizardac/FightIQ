import os
import asyncio
import sys

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import VISUALS_DIR, ASSETS_DIR, DATA_DIR
from core.naming import safe_filename_lower

# Ensure we can find installed packages
try:
    # MoviePy 2.x uses 'moviepy' directly; 1.x used 'moviepy.editor'
    try:
        from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, ColorClip
    except ImportError:
        from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, ColorClip

    import edge_tts
    import PIL.Image

    # MONKEY PATCH: Fix for Pillow 10+ removing ANTIALIAS
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

    _VIDEO_ENABLED = True
except ImportError as e:
    print(f"⚠️ VIDEO ENGINE WARNING: {e}")
    print("Video generation will be disabled.")
    ImageClip = object
    AudioFileClip = object
    CompositeVideoClip = object
    ColorClip = object
    _VIDEO_ENABLED = False

# ==========================================
# 🎥 FIGHTIQ: VIDEO ENGINE -> 10_video_engine.py
# ==========================================

BACKGROUND_MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
OUTPUT_DIR = VISUALS_DIR
# Temp audio file lives in data/ to avoid polluting project root
_VOICE_TEMP = os.path.join(DATA_DIR, "voice_temp.mp3")

async def generate_voiceover(text, filename=None):
    """Generates a gritty AI voiceover using Edge-TTS."""
    if filename is None:
        filename = _VOICE_TEMP
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    VOICE = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filename)
    return filename

def create_reel(fighter_name, image_path, script_text, output_filename=None):
    print(f"   🎬 Action: Creating Reel for {fighter_name}...")
    
    if not os.path.exists(image_path):
        print(f"      ❌ Image not found: {image_path}")
        return None

    if not output_filename:
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        safe_name = safe_filename_lower(fighter_name)
        output_filename = os.path.join(OUTPUT_DIR, f"Reel_{safe_name}.mp4")

    # 1. AUDIO LAYER
    voice_file = _VOICE_TEMP
    try:
        if os.path.exists(voice_file):
            os.remove(voice_file)
        asyncio.run(generate_voiceover(script_text, voice_file))
        voice_clip = AudioFileClip(voice_file)
        duration = voice_clip.duration + 1.0
    except Exception as e:
        print(f"      ⚠️ TTS Failed: {e}")
        return None

    # 2. VISUAL LAYER  (MoviePy 2.x API: with_* instead of set_*)
    try:
        img_clip = ImageClip(image_path).with_duration(duration)
        # 720-wide portrait keeps file small and encoding fast
        img_clip = img_clip.resized(width=720)

        bg_clip = ColorClip(size=(720, 1280), color=(10, 10, 10), duration=duration)
        video = CompositeVideoClip([bg_clip, img_clip.with_position("center")])

    except Exception as e:
        print(f"      ❌ Video Compositing Failed: {e}")
        return None

    # 3. EXPORT
    try:
        final_video = video.with_audio(voice_clip)
        final_video.write_videofile(
            output_filename,
            fps=15,
            codec="libx264",
            audio_codec="aac",
            threads=2,
            preset="ultrafast",
            logger=None
        )
        voice_clip.close()
        if os.path.exists(voice_file):
            os.remove(voice_file)

        print(f"      ✅ Reel Saved: {output_filename}")
        return output_filename

    except Exception as e:
        print(f"      ❌ Export Failed: {e}")
        return None

def create_matchup_reel(radar_chart_path, prediction_script, f1_name, f2_name, output_filename=None):
    """
    Creates a matchup video from a radar chart with voiceover.
    Designed for FIGHT WEEK mode.
    
    Args:
        radar_chart_path: Path to radar chart PNG
        prediction_script: Text script for voiceover
        f1_name: Fighter 1 name
        f2_name: Fighter 2 name
        output_filename: Optional custom output path
    
    Returns:
        str: Path to generated video, or None if failed
    """
    print(f"   🎬 Creating Matchup Reel: {f1_name} vs {f2_name}...")
    
    if not os.path.exists(radar_chart_path):
        print(f"      ❌ Radar chart not found: {radar_chart_path}")
        return None
    
    if not output_filename:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        safe_f1 = safe_filename_lower(f1_name)
        safe_f2 = safe_filename_lower(f2_name)
        output_filename = os.path.join(OUTPUT_DIR, f"Reel_Matchup_{safe_f1}_vs_{safe_f2}.mp4")
    
    # 1. AUDIO LAYER
    voice_file = _VOICE_TEMP
    try:
        if os.path.exists(voice_file):
            os.remove(voice_file)
        asyncio.run(generate_voiceover(prediction_script, voice_file))
        voice_clip = AudioFileClip(voice_file)
        duration = voice_clip.duration + 0.5  # Small padding
    except Exception as e:
        print(f"      ⚠️ TTS Failed: {e}")
        return None
    
    # 2. VISUAL LAYER — MoviePy 2.x API (static scale; dynamic lambdas cause hang)
    try:
        img_clip = ImageClip(radar_chart_path).with_duration(duration)
        img_clip = img_clip.resized(width=720)
        bg_clip = ColorClip(size=(720, 1280), color=(10, 10, 10), duration=duration)
        video = CompositeVideoClip([bg_clip, img_clip.with_position("center")])

    except Exception as e:
        print(f"      ❌ Video Compositing Failed: {e}")
        return None

    # 3. EXPORT
    try:
        final_video = video.with_audio(voice_clip)
        final_video.write_videofile(
            output_filename,
            fps=15,
            codec="libx264",
            audio_codec="aac",
            threads=2,
            preset="ultrafast",
            logger=None
        )
        voice_clip.close()
        if os.path.exists(voice_file):
            os.remove(voice_file)

        print(f"      ✅ Matchup Reel Saved: {output_filename}")
        return output_filename

    except Exception as e:
        print(f"      ❌ Export Failed: {e}")
        return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FightIQ Video Engine Test")
    parser.add_argument("--image", required=True, help="Path to fighter card image")
    parser.add_argument("--name", default="Test Fighter", help="Fighter name")
    parser.add_argument("--script", default="This is a test voiceover.", help="Script text")
    args = parser.parse_args()

    print("--- TESTING VIDEO ENGINE ---")
    result = create_reel(args.name, args.image, args.script)
    if result:
        print(f"✅ Video created: {result}")
    else:
        print("❌ Video creation failed.")
