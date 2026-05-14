import os
import asyncio
import sys

# Ensure we can find installed packages
try:
    from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, ColorClip
    import edge_tts
    import PIL.Image
    
    # MONKEY PATCH: Fix for Pillow 10+ removing ANTIALIAS
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    print(f"Python Executable: {sys.executable}")
    sys.exit(1)

# ==========================================
# 🎥 FIGHTIQ: VIDEO ENGINE -> 10_video_engine.py
# ==========================================

BACKGROUND_MUSIC_DIR = "assets/music"
OUTPUT_DIR = "visuals"

async def generate_voiceover(text, filename="voice_temp.mp3"):
    """Generates a gritty AI voiceover using Edge-TTS."""
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
        safe_name = fighter_name.replace(" ", "_").lower()
        output_filename = os.path.join(OUTPUT_DIR, f"Reel_{safe_name}.mp4")

    # 1. AUDIO LAYER
    voice_file = "voice_temp.mp3"
    try:
        if os.path.exists(voice_file): os.remove(voice_file)
        asyncio.run(generate_voiceover(script_text, voice_file))
        voice_clip = AudioFileClip(voice_file)
        duration = voice_clip.duration + 1.0 
    except Exception as e:
        print(f"      ⚠️ TTS Failed: {e}")
        return None

    # 2. VISUAL LAYER
    try:
        img_clip = ImageClip(image_path).set_duration(duration)
        
        # Resize logic
        # Target: 1080x1920 (9:16)
        # We will resize image to width 1080, and place on black BG
        img_clip = img_clip.resize(width=1080)
        
        # Background
        bg_clip = ColorClip(size=(1080, 1920), color=(10,10,10), duration=duration)
        
        # Zoom Effect: simple 5% zoom
        # Note: MoviePy v2 might use effects.vfx.Resize. v1 uses clip.resize
        img_zoomed = img_clip.resize(lambda t : 1 + 0.05 * (t / duration)) 
        
        # Center
        video = CompositeVideoClip([bg_clip, img_zoomed.set_position("center")])
        
    except Exception as e:
        print(f"      ❌ Video Compositing Failed: {e}")
        return None

    # 3. EXPORT
    try:
        final_video = video.set_audio(voice_clip)
        final_video.write_videofile(
            output_filename, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            threads=4,
            preset="ultrafast", # Faster for testing
            logger=None
        )
        voice_clip.close()
        # cleanup
        if os.path.exists(voice_file): os.remove(voice_file)
        
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
        safe_f1 = f1_name.replace(" ", "_").lower()
        safe_f2 = f2_name.replace(" ", "_").lower()
        output_filename = os.path.join(OUTPUT_DIR, f"Reel_Matchup_{safe_f1}_vs_{safe_f2}.mp4")
    
    # 1. AUDIO LAYER
    voice_file = "voice_temp.mp3"
    try:
        if os.path.exists(voice_file):
            os.remove(voice_file)
        asyncio.run(generate_voiceover(prediction_script, voice_file))
        voice_clip = AudioFileClip(voice_file)
        duration = voice_clip.duration + 0.5  # Small padding
    except Exception as e:
        print(f"      ⚠️ TTS Failed: {e}")
        return None
    
    # 2. VISUAL LAYER - Radar Chart with Zoom Effect
    try:
        img_clip = ImageClip(radar_chart_path).set_duration(duration)
        
        # Target dimensions: 1080x1920 (9:16 vertical)
        # Radar charts are usually square, so we need to fit them properly
        img_clip = img_clip.resize(width=1080)
        
        # Background
        bg_clip = ColorClip(size=(1080, 1920), color=(10, 10, 10), duration=duration)
        
        # Zoom effect: Start at 1.0x, end at 1.15x
        # Smoother zoom with easeInOut
        def zoom_function(t):
            progress = t / duration
            # Ease in-out function for smooth zoom
            if progress < 0.5:
                eased = 2 * progress * progress
            else:
                eased = 1 - pow(-2 * progress + 2, 2) / 2
            return 1.0 + (0.15 * eased)
        
        img_zoomed = img_clip.resize(zoom_function)
        
        # Center the zoomed radar chart
        video = CompositeVideoClip([bg_clip, img_zoomed.set_position("center")])
        
    except Exception as e:
        print(f"      ❌ Video Compositing Failed: {e}")
        return None
    
    # 3. EXPORT
    try:
        final_video = video.set_audio(voice_clip)
        final_video.write_videofile(
            output_filename,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="ultrafast",
            logger=None
        )
        voice_clip.close()
        
        # Cleanup
        if os.path.exists(voice_file):
            os.remove(voice_file)
        
        print(f"      ✅ Matchup Reel Saved: {output_filename}")
        return output_filename
    
    except Exception as e:
        print(f"      ❌ Export Failed: {e}")
        return None

if __name__ == "__main__":

    print("--- TESTING VIDEO ENGINE ---")
    # Use the absolute path provided by previous step's artifact creation if possible,
    # or failing that, use a placeholder.
    # User's artifact path: C:\Users\Deniz\.gemini\antigravity\brain\8c7579cb-2be3-40fa-8e5e-3e77bdc8f2fa\test_card_conor_mcgregor_1768504006478.png
    
    # We will pass this as an argument or hardcode for this test run
    test_img = r"C:\Users\Deniz\.gemini\antigravity\brain\8c7579cb-2be3-40fa-8e5e-3e77bdc8f2fa\test_card_conor_mcgregor_1768504006478.png"
    
    create_reel(
        "Conor McGregor", 
        test_img, 
        "The Notorious Conor McGregor returns with a ninety nine power rating. The king is back."
    )
