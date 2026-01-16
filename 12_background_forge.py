import google.generativeai as genai
import os
import sys
import json
from dotenv import load_dotenv
from PIL import Image
import io

# ==========================================
# 🎨 FIGHTIQ: BACKGROUND FORGE (Nano Banana)
# ==========================================

OUTPUT_DIR = "assets/backgrounds"
CACHE_FILE = "assets/background_cache.json"

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Load environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found in .env")
    sys.exit(1)

genai.configure(api_key=api_key)

# Import config
try:
    import config
    IMAGEN_MODEL = config.IMAGEN_MODEL
except:
    IMAGEN_MODEL = "models/imagen-4.0-generate"

def load_cache():
    """Load cache of generated backgrounds"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    """Save cache"""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def sanitize_nickname(nickname):
    """Clean nickname for filename"""
    return "".join([c for c in nickname if c.isalnum() or c in " -_"]).replace(" ", "_")

def generate_fighter_background(nickname, force_regenerate=False):
    """
    Generate a cinematic MMA background using Imagen AI.
    
    Args:
        nickname: Fighter nickname (e.g., "The Korean Zombie", "The Notorious")
        force_regenerate: If True, regenerate even if cached
    
    Returns:
        str: Path to generated background image, or None if failed
    """
    print(f"\n🎨 BACKGROUND FORGE: Processing '{nickname}'...")
    
    # Check cache
    cache = load_cache()
    safe_name = sanitize_nickname(nickname)
    
    if not force_regenerate and safe_name in cache:
        cached_path = cache[safe_name]
        if os.path.exists(cached_path):
            print(f"   ✅ Using cached background: {cached_path}")
            return cached_path
        else:
            print(f"   ⚠️ Cached file missing, regenerating...")
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Prompt Engineering for Imagen
    prompt = f"""A dark, cinematic MMA octagon background texture inspired by the fighter nickname "{nickname}". 
Neon lighting, cyberpunk aesthetic, high contrast, moody atmosphere. 
Abstract and artistic, suitable as a background overlay. 
No text, no people, no logos. Professional sports photography style. 
4K resolution, dramatic shadows, intense colors."""
    
    print(f"   📝 Prompt: {prompt[:80]}...")
    
    try:
        # Call Imagen API
        print(f"   🔮 Calling Imagen model: {IMAGEN_MODEL}")
        
        # Initialize the model
        model = genai.ImageGenerationModel(IMAGEN_MODEL)
        
        # Generate image
        response = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            safety_filter_level="block_only_high",  # Allow creative content
            aspect_ratio="9:16",  # Vertical format for cards
            person_generation="allow_adult"  # For fighter-themed imagery
        )
        
        # Check if we got images
        if not response.images:
            print(f"   ❌ No images returned from API")
            return None
        
        # Get the first image
        generated_image = response.images[0]
        
        # Save image
        output_path = os.path.join(OUTPUT_DIR, f"{safe_name}.png")
        
        # The response.images contains PIL Images
        generated_image._pil_image.save(output_path, "PNG")
        
        print(f"   ✅ Background generated: {output_path}")
        
        # Update cache
        cache[safe_name] = output_path
        save_cache(cache)
        
        return output_path
    
    except AttributeError as e:
        # Alternative API structure
        print(f"   ⚠️ Trying alternative Imagen API structure...")
        try:
            # Try direct generate method
            imagen = genai.GenerativeModel(IMAGEN_MODEL)
            response = imagen.generate_content(prompt)
            
            # This might return base64 or different format
            # For now, return None and we'll use manual generation
            print(f"   ⚠️ Imagen API structure different than expected")
            print(f"   💡 Recommendation: Generate backgrounds manually or use stock images")
            return None
            
        except Exception as e2:
            print(f"   ❌ Alternative method failed: {e2}")
            return None
    
    except Exception as e:
        print(f"   ❌ Background generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def batch_generate_popular_themes():
    """
    Generate backgrounds for common fighter themes ahead of time.
    This saves API calls during fight week.
    """
    print("=" * 60)
    print("🎨 BATCH BACKGROUND GENERATION")
    print("=" * 60)
    
    # Common fighter nickname themes
    themes = [
        "The Destroyer",
        "The Dragon",
        "The Assassin",
        "The Beast",
        "The Pitbull",
        "The Spider",
        "The Axe Murderer",
        "The Nightmare",
        "The Predator",
        "The Lion",
        "The Eagle",
        "The Irish",
        "The Korean Zombie",
        "The Notorious",
        "Blessed",
        "The Violence King",
        "The Soldier",
        "The Maverick",
        "The Immortal",
        "The Phenom"
    ]
    
    successful = 0
    failed = 0
    
    for theme in themes:
        result = generate_fighter_background(theme)
        if result:
            successful += 1
        else:
            failed += 1
        
        # Delay between API calls to avoid rate limiting
        import time
        time.sleep(3)
    
    print(f"\n{'='*60}")
    print(f"✅ Batch Complete:")
    print(f"   Successful: {successful}/{len(themes)}")
    print(f"   Failed: {failed}/{len(themes)}")
    print(f"   Total Cost: ~${successful * 0.04:.2f} (at $0.04/image)")
    print(f"{'='*60}")

def main():
    print("--- 🎨 BACKGROUND FORGE (Nano Banana) ---")
    print("\nOptions:")
    print("1. Generate single background")
    print("2. Batch generate popular themes")
    print("3. Regenerate existing (force)")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        nickname = input("Enter fighter nickname: ").strip()
        if nickname:
            result = generate_fighter_background(nickname)
            if result:
                print(f"\n✅ SUCCESS: {result}")
            else:
                print(f"\n❌ FAILED")
    
    elif choice == "2":
        confirm = input("This will generate 20 backgrounds (~$0.80 cost). Continue? (y/n): ")
        if confirm.lower() == 'y':
            batch_generate_popular_themes()
    
    elif choice == "3":
        nickname = input("Enter fighter nickname to regenerate: ").strip()
        if nickname:
            result = generate_fighter_background(nickname, force_regenerate=True)
            if result:
                print(f"\n✅ SUCCESS: {result}")
            else:
                print(f"\n❌ FAILED")
    else:
        print("Invalid option")

if __name__ == "__main__":
    main()
