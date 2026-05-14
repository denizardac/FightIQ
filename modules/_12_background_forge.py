"""
🎨 FIGHTIQ: BACKGROUND FORGE (Nano Banana)
AI-powered background generation using Imagen
UPDATED: Using new google.genai package
"""

from google import genai
from google.genai import types
import os
import sys
import json
from dotenv import load_dotenv
from PIL import Image
import io

# ==========================================
# CONFIGURATION
# ==========================================

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import ASSETS_DIR

# ==========================================
# CONFIGURATION
# ==========================================

OUTPUT_DIR = os.path.join(ASSETS_DIR, "backgrounds")
CACHE_FILE = os.path.join(ASSETS_DIR, "background_cache.json")

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

# Initialize client
client = genai.Client(api_key=api_key)

# Import config
try:
    import core.config as config
    IMAGEN_MODEL = config.IMAGEN_MODEL
except:
    IMAGEN_MODEL = "models/imagen-4.0-generate-preview-06-06"

# ==========================================
# CACHE MANAGEMENT
# ==========================================

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

# ==========================================
# BACKGROUND GENERATION
# ==========================================

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
    print(f"   🔮 Using model: {IMAGEN_MODEL}")
    
    try:
        # Generate image using new API
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1
                # Note: aspect_ratio, safety_filter_level, person_generation not supported in this API version
            )
        )
        
        # Check if we got images
        if not response.generated_images:
            print(f"   ❌ No images returned from API")
            return None
        
        # Get the first image
        generated_image = response.generated_images[0]
        
        # Convert to PIL Image
        image_data = generated_image.image.image_bytes
        pil_image = Image.open(io.BytesIO(image_data))
        
        # Save image
        output_path = os.path.join(OUTPUT_DIR, f"{safe_name}.png")
        pil_image.save(output_path, "PNG")
        
        print(f"   ✅ Background generated: {output_path}")
        print(f"   💰 Cost: ~$0.04")
        
        # Update cache
        cache[safe_name] = output_path
        save_cache(cache)
        
        return output_path
    
    except Exception as e:
        print(f"   ❌ Background generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==========================================
# BATCH GENERATION
# ==========================================

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
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"✅ Batch Complete:")
    print(f"   Successful: {successful}/{len(themes)}")
    print(f"   Failed: {failed}/{len(themes)}")
    print(f"   Total Cost: ~${successful * 0.04:.2f} (at $0.04/image)")
    print(f"{'='*60}")

# ==========================================
# TICKET BACKGROUND GENERATION
# ==========================================

def generate_ticket_background(slip_type):
    """
    Generate optimized background for betting tickets.
    
    Args:
        slip_type: 'safe', 'violence', or 'value'
    
    Returns:
        str: Path to background image
    """
    # Theme-specific prompts
    prompts = {
        "safe": "Professional betting slip background, dark green gradient, subtle hexagon pattern, minimalist, premium sports betting aesthetic, 4K",
        "violence": "Intense MMA background, blood red gradient, aggressive textures, fire sparks, dramatic lighting, UFC octagon vibes, 4K",
        "value": "Sharp money betting background, electric blue cyan gradient, data visualization patterns, futuristic HUD elements, premium analytics aesthetic, 4K"
    }
    
    prompt = prompts.get(slip_type, prompts["safe"])
    
    print(f"\n🎨 Generating {slip_type.upper()} ticket background...")
    print(f"   📝 Prompt: {prompt[:60]}...")
    
    try:
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1
            )
        )
        
        if response.generated_images:
            image_data = response.generated_images[0].image.image_bytes
            pil_image = Image.open(io.BytesIO(image_data))
            
            # Save
            os.makedirs(os.path.join(ASSETS_DIR, "ticket_backgrounds"), exist_ok=True)
            output_path = os.path.join(ASSETS_DIR, "ticket_backgrounds", f"{slip_type}_bg.png")
            pil_image.save(output_path, "PNG")
            
            print(f"   ✅ Saved: {output_path}")
            print(f"   💰 Cost: ~$0.04")
            return output_path
        else:
            print(f"   ❌ No image generated")
            return None
    
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return None

# ==========================================
# MAIN MENU
# ==========================================

def main():
    print("=" * 60)
    print("🎨 BACKGROUND FORGE (Nano Banana)")
    print("   Using: google.genai (New API)")
    print("=" * 60)
    print("\nOptions:")
    print("1. Generate single fighter background")
    print("2. Batch generate popular themes (20 backgrounds)")
    print("3. Generate ticket backgrounds (3 backgrounds)")
    print("4. Regenerate existing (force)")
    
    choice = input("\nSelect option (1-4): ").strip()
    
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
        confirm = input("Generate 3 ticket backgrounds (~$0.12 cost). Continue? (y/n): ")
        if confirm.lower() == 'y':
            for slip_type in ["safe", "violence", "value"]:
                generate_ticket_background(slip_type)
    
    elif choice == "4":
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
