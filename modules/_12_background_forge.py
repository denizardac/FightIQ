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
import hashlib
from dotenv import load_dotenv
from PIL import Image, ImageDraw

# ==========================================
# CONFIGURATION
# ==========================================

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import ASSETS_DIR, PROJECT_ROOT
from core.imagen_utils import generate_imagen_image

# ==========================================
# CONFIGURATION
# ==========================================

OUTPUT_DIR = os.path.join(ASSETS_DIR, "backgrounds")
CACHE_FILE = os.path.join(ASSETS_DIR, "background_cache.json")

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Load environment (project root — not dependent on cwd)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
if not api_key:
    print("⚠️ GEMINI_API_KEY not set — Imagen disabled; gradient fallbacks will be used.")

# Import config (Imagen model ids)
try:
    import core.config as config  # noqa: F401
except Exception:
    pass

# ==========================================
# CACHE MANAGEMENT
# ==========================================

def load_cache():
    """Load cache of generated backgrounds"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
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


def _gradient_portrait_background(seed: str, width=1080, height=1350):
    """Deterministic premium gradient when Imagen is unavailable or fails."""
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).digest()
    glow = (30 + digest[0] % 120, 20 + digest[1] % 140, 40 + digest[2] % 120)
    mid = (digest[3] % 45, digest[4] % 40, digest[5] % 50)
    dark = (6 + digest[6] % 12, 6 + digest[7] % 10, 10 + digest[8] % 14)
    img = Image.new("RGB", (width, height), dark)
    dr = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        if ratio < 0.32:
            f = ratio / 0.32
            r = int(glow[0] * 0.22 * (1 - f) + mid[0] * f)
            g = int(glow[1] * 0.22 * (1 - f) + mid[1] * f)
            b = int(glow[2] * 0.22 * (1 - f) + mid[2] * f)
        else:
            f = (ratio - 0.32) / 0.68
            r = int(mid[0] * (1 - f) + dark[0] * f)
            g = int(mid[1] * (1 - f) + dark[1] * f)
            b = int(mid[2] * (1 - f) + dark[2] * f)
        dr.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _ticket_gradient(slip_type, width=1080, height=1600):
    """Match ticket canvas proportions (same palette idea as hybrid ticket module)."""
    colors = {
        "safe": ((0, 255, 65), (5, 20, 5), (2, 5, 2)),
        "violence": ((255, 0, 85), (20, 5, 5), (5, 2, 2)),
        "value": ((255, 215, 0), (20, 18, 5), (5, 4, 1)),
    }
    glow, mid, dark = colors.get(slip_type, ((80, 80, 90), (20, 20, 22), (6, 6, 8)))
    img = Image.new("RGB", (width, height), dark)
    dr = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        if ratio < 0.3:
            f = ratio / 0.3
            r = int(glow[0] * 0.15 * (1 - f) + mid[0] * f)
            g = int(glow[1] * 0.15 * (1 - f) + mid[1] * f)
            b = int(glow[2] * 0.15 * (1 - f) + mid[2] * f)
        else:
            f = (ratio - 0.3) / 0.7
            r = int(mid[0] * (1 - f) + dark[0] * f)
            g = int(mid[1] * (1 - f) + dark[1] * f)
            b = int(mid[2] * (1 - f) + dark[2] * f)
        dr.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _persist_fighter_fallback(nickname, safe_name):
    """Write gradient file and update cache."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{safe_name}.png")
    _gradient_portrait_background(nickname).save(output_path, "PNG")
    cache = load_cache()
    cache[safe_name] = output_path
    save_cache(cache)
    print(f"   ✅ Saved gradient fallback: {output_path}")
    return output_path

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
    print("   🔮 Imagen (auto model fallback)")

    if not client:
        print("   ⚠️ No API client — writing gradient fallback.")
        return _persist_fighter_fallback(nickname, safe_name)

    pil_image = generate_imagen_image(
        client,
        prompt,
        types.GenerateImagesConfig(number_of_images=1),
    )
    if pil_image is None:
        print("   ❌ No image from Imagen — using gradient fallback.")
        return _persist_fighter_fallback(nickname, safe_name)

    output_path = os.path.join(OUTPUT_DIR, f"{safe_name}.png")
    pil_image.save(output_path, "PNG")

    print(f"   ✅ Background generated: {output_path}")
    print(f"   💰 Cost: ~$0.04")

    cache[safe_name] = output_path
    save_cache(cache)

    return output_path

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

    out_dir = os.path.join(ASSETS_DIR, "ticket_backgrounds")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{slip_type}_bg.png")

    if not client:
        print("   ⚠️ No API client — saving gradient ticket background.")
        _ticket_gradient(slip_type).save(output_path, "PNG")
        print(f"   ✅ Saved (gradient): {output_path}")
        return output_path

    pil = generate_imagen_image(
        client,
        prompt,
        types.GenerateImagesConfig(number_of_images=1),
    )
    if pil is not None:
        pil.save(output_path, "PNG")
        print(f"   ✅ Saved: {output_path}")
        print(f"   💰 Cost: ~$0.04")
        return output_path

    print(f"   ❌ No image from Imagen — gradient fallback.")

    _ticket_gradient(slip_type).save(output_path, "PNG")
    print(f"   ✅ Saved (gradient): {output_path}")
    return output_path

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
