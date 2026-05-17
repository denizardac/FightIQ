"""
🎫 FIGHTIQ: HYBRID TICKET GENERATOR V10
Combines AI-generated backgrounds with precise PIL text rendering

PHILOSOPHY: AI for art, PIL for data accuracy
- Imagen generates text-free themed backgrounds
- PIL renders all text with 100% accuracy
- Result: Viral-quality visuals + Perfect data
"""

import json
import os
import re
import sys
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR, ASSETS_DIR, PROJECT_ROOT
from core.odds_converter import american_to_decimal
from core.imagen_utils import generate_imagen_image

try:
    import core.config as config
except Exception:
    config = None

OUTPUT_DIR = VISUALS_DIR
INPUT_FILE = get_data_path("4_parlays.json")
BG_CACHE_DIR = os.path.join(ASSETS_DIR, "ticket_backgrounds")

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Initialize (.env next to project root — cwd-independent)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# ===========================================
# TEXT-FREE BACKGROUND PROMPTS (NO TEXT!)
# ===========================================
BACKGROUND_PROMPTS = {
    "safe": {
        "theme_name": "The Clean Bank",
        "prompt": """Abstract minimalist premium sports UI aesthetic, vertical composition.
Clean studio lighting with a subtle electric green (#00FF41) glow.
Smooth dark surfaces, subtle carbon fiber or matte black textures.
Minimalist, elegant, high-end professional atmosphere.
Deep black background (#0a0a0a) with very sparse emerald green neon accents.

ABSOLUTELY NO TEXT. NO GRID LINES. NO CLUTTER.
Ultra-clean minimalist abstract design.
Vertical format 1080x1350px.""",
        "accent_color": "#00FF41",
        "secondary_color": "#FFFFFF"
    },
    
    "violence": {
        "theme_name": "The Crimson Void",
        "prompt": """Abstract minimalist aggressive aura aesthetic, vertical composition.
Deep crimson red (#FF0055) ambient lighting fading into pitch black.
Subtle smoke or dark vapor, very clean gradient transitions.
Ominous, intense, but highly minimalist atmosphere.
Matte black base with dark red glowing edges.

ABSOLUTELY NO TEXT. NO EXPLOSIONS. NO CLUTTER.
Ultra-clean minimalist abstract design.
Vertical format 1080x1350px.""",
        "accent_color": "#FF0055",
        "secondary_color": "#FFFFFF"
    },
    
    "value": {
        "theme_name": "The Dark Gold",
        "prompt": """Abstract luxury minimalist aesthetic, vertical composition.
Premium dark theme with subtle gold (#FFD700) illuminated outlines.
Smooth onyx or polished dark stone textures, extremely clean.
VIP exclusive atmosphere, highly refined.
Deep black base with a touch of elegant gold light.

ABSOLUTELY NO TEXT. NO CLUTTER. NO HEAVY PATTERNS.
Ultra-clean minimalist abstract design.
Vertical format 1080x1350px.""",
        "accent_color": "#FFD700",
        "secondary_color": "#FFFFFF"
    }
}

# ===========================================
# FONT LOADING
# ===========================================
def load_font(font_key, size):
    """Load bundled fonts from project root (VPS-safe); fall back to Arial."""
    defaults = {
        "headline": os.path.join(ASSETS_DIR, "fonts", "BebasNeue-Regular.ttf"),
        "body": os.path.join(ASSETS_DIR, "fonts", "Roboto-Bold.ttf"),
        "regular": os.path.join(ASSETS_DIR, "fonts", "Roboto-Regular.ttf"),
    }
    path = defaults.get(font_key, defaults["body"])
    try:
        if config and hasattr(config, "FONT_PATHS"):
            cfg_key = {"headline": "headline", "body": "body_bold", "regular": "body_regular"}.get(font_key, font_key)
            rel = config.FONT_PATHS.get(cfg_key) or config.FONT_PATHS.get("body_bold")
            if rel:
                path = rel if os.path.isabs(rel) else os.path.join(PROJECT_ROOT, *rel.replace("/", os.sep).split(os.sep))
    except Exception:
        pass
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
    except Exception:
        pass
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

# ===========================================
# BACKGROUND GENERATION
# ===========================================
def get_or_generate_background(slip_type):
    """Get cached background or generate new one"""
    
    os.makedirs(BG_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(BG_CACHE_DIR, f"bg_{slip_type}.png")
    
    # Use cached if exists
    if os.path.exists(cache_path):
        print(f"   📁 Using cached background: {cache_path}")
        bg = Image.open(cache_path).convert("RGB")
        # Ensure it fits the new taller canvas
        return bg.resize((1080, 1600), Image.LANCZOS)
    
    # Generate new background
    if not client:
        print(f"   ⚠️ No API client, using gradient fallback")
        return create_gradient_background(slip_type)
    
    theme = BACKGROUND_PROMPTS.get(slip_type, BACKGROUND_PROMPTS["safe"])
    print(f"   🎨 Generating AI background: {theme['theme_name']}...")

    bg = generate_imagen_image(
        client,
        theme["prompt"],
        types.GenerateImagesConfig(number_of_images=1),
    )
    if bg is not None:
        bg = bg.resize((1080, 1600), Image.LANCZOS)
        bg.save(cache_path, "PNG")
        print(f"   ✅ Background generated and cached ($0.04)")
        return bg

    print(f"   ⚠️ AI generation failed for all Imagen models, using gradient fallback")
    return create_gradient_background(slip_type)

def create_gradient_background(slip_type):
    """Create premium gradient fallback with subtle glowing aura at the top"""
    WIDTH, HEIGHT = 1080, 1600 # Taller Canvas
    
    colors = {
        "safe": ((0, 255, 65), (5, 20, 5), (2, 5, 2)),
        "violence": ((255, 0, 85), (20, 5, 5), (5, 2, 2)),
        "value": ((255, 215, 0), (20, 18, 5), (5, 4, 1))
    }
    
    glow, mid, dark = colors.get(slip_type, ((100, 100, 100), (20, 20, 20), (5, 5, 5)))
    
    img = Image.new('RGB', (WIDTH, HEIGHT), dark)
    draw = ImageDraw.Draw(img)
    
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        
        # Interpolate Glow -> Mid -> Dark to create a deep, premium lighting effect
        if ratio < 0.3:
            # Top 30%: Subtle Glow transitioning to Mid
            factor = ratio / 0.3
            r = int(glow[0]*0.15 * (1-factor) + mid[0] * factor)
            g = int(glow[1]*0.15 * (1-factor) + mid[1] * factor)
            b = int(glow[2]*0.15 * (1-factor) + mid[2] * factor)
        else:
            # Bottom 70%: Mid transitioning to Dark abyss
            factor = (ratio - 0.3) / 0.7
            r = int(mid[0] * (1-factor) + dark[0] * factor)
            g = int(mid[1] * (1-factor) + dark[1] * factor)
            b = int(mid[2] * (1-factor) + dark[2] * factor)
            
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    
    return img

# ===========================================
# DATA EXTRACTION
# ===========================================
def extract_odds(pick):
    """Extract decimal odds from pick (float, dict with decimal/american, or @ in text)."""
    raw = pick.get("odds")
    if raw is not None and raw != "" and raw != 0:
        if isinstance(raw, dict):
            if raw.get("decimal") is not None:
                try:
                    d = float(raw["decimal"])
                    if d > 1.0:
                        return round(d, 2)
                except (TypeError, ValueError):
                    pass
            if raw.get("american") is not None:
                try:
                    d = american_to_decimal(str(raw["american"]).replace("+", ""))
                    if d > 1.0:
                        return round(d, 2)
                except Exception:
                    pass
        elif isinstance(raw, str):
            s = raw.strip().replace(",", ".")
            if s.startswith(("+", "-")) and re.match(r"^[+-]\d{3,}$", s):
                try:
                    d = american_to_decimal(s)
                    if d > 1.0:
                        return round(d, 2)
                except Exception:
                    pass
            try:
                d = float(s)
                if d > 50:
                    d = american_to_decimal(int(d))
                if 1.01 <= d <= 100:
                    return round(d, 2)
            except (TypeError, ValueError):
                pass
        else:
            try:
                d = float(raw)
                if d > 50:
                    d = american_to_decimal(int(d))
                if 1.01 <= d <= 100:
                    return round(d, 2)
            except (TypeError, ValueError):
                pass

    pick_text = pick.get("pick", "") or ""
    reason = pick.get("reason", "") or ""

    for blob in (pick_text, reason):
        if "@" in blob:
            try:
                tail = blob.split("@", 1)[1].strip().split()
                if tail:
                    d = float(tail[0].replace(",", "."))
                    if 1.01 <= d <= 100:
                        return round(d, 2)
            except (IndexError, ValueError, TypeError):
                pass

    return None


def calculate_parlay_odds(slip_data):
    """Product of valid decimal odds only (no fabricated defaults)."""
    total = 1.0
    n = 0
    max_legs = getattr(config, "PARLAY_MAX_LEGS", 3) if config else 3
    for pick in slip_data[:max_legs]:
        o = extract_odds(pick)
        if o is not None and o > 1.0:
            total *= o
            n += 1
    return round(total, 2) if n else 1.0

def format_match_name(match):
    """Format match for display"""
    if ' vs ' in match:
        fighters = match.split(' vs ')
        f1 = fighters[0].strip().split()[-1]
        f2 = fighters[1].strip().split()[-1] if len(fighters) > 1 else ""
        return f"{f1} vs {f2}"
    return match[:30]

# ===========================================
# PIL TEXT RENDERING (100% ACCURATE)
# ===========================================
def render_data_layer(slip_data, slip_type, total_odds, win_amount):
    """
    Render all text onto transparent layer with PIL.
    This ensures 100% data accuracy - no hallucinations!
    """
    WIDTH, HEIGHT = 1080, 1600 # Expanded canvas to accommodate new box heights
    
    # Create transparent overlay
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Apply global dark tint (Subtle! Reduced to 100 so AI textures shine beautifully)
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=(10, 10, 12, 100))
    
    theme = BACKGROUND_PROMPTS.get(slip_type, BACKGROUND_PROMPTS["safe"])
    accent = theme["accent_color"]
    secondary = theme["secondary_color"]
    
    # Load fonts (Strictly managed typography scales to prevent overlaps)
    font_title = load_font("headline", 90) # Main titles: Thick BebasNeue
    font_subtitle = load_font("headline", 46)
    font_pick_title_base = load_font("headline", 44) 
    font_odds = load_font("headline", 86) # Reduced from 110 for better footer balance
    font_small = load_font("regular", 24)
    
    # ===========================================
    # HEADER SECTION
    # ===========================================
    y = 40
    
    slip_titles = {
        "safe": ("SAFE SLIP", "SUREFIRE PARLAY"),
        "violence": ("VIOLENCE SLIP", "FINISH GUARANTEED"),
        "value": ("EDGE SLIP", "MODEL PARLAY")
    }
    title, subtitle = slip_titles.get(slip_type, slip_titles["safe"])
    
    # Draw title with heavy shadow
    draw.text((WIDTH//2 + 3, y + 3), title, font=font_title, fill="#000000", anchor="mt")
    draw.text((WIDTH//2, y), title, font=font_title, fill=accent, anchor="mt")
    y += 85
    
    draw.text((WIDTH//2 + 2, y + 2), subtitle, font=font_subtitle, fill="#000000", anchor="mt")
    draw.text((WIDTH//2, y), subtitle, font=font_subtitle, fill="#EEEEEE", anchor="mt")
    y += 55
    
    # Separator line
    draw.line([(120, y+2), (WIDTH-120, y+2)], fill="#000000", width=4)
    draw.line([(120, y), (WIDTH-120, y)], fill=accent, width=3)
    y += 40
    
    # ===========================================
    # PICKS SECTION (TALE OF THE TAPE: DUAL DUEL)
    # ===========================================
    max_legs = getattr(config, "PARLAY_MAX_LEGS", 3) if config else 3
    for i, pick in enumerate(slip_data[:max_legs], 1):
        match = pick.get('match', 'Unknown')
        pick_text = pick.get('pick', 'Unknown')
        odds = extract_odds(pick)
        odds_label = f"@ {odds:.2f}" if (odds is not None and odds > 1.0) else "@ —"
        match_display = format_match_name(match)
        
        fighters = match.split(' vs ')
        f1_name = fighters[0].strip()
        f2_name = fighters[1].strip() if len(fighters) > 1 else ""
        
        box_y = y
        box_h = 160 # Expanded box height to safely contain the 3-tier center stack
        
        # Background Box
        draw.rounded_rectangle([(40, box_y), (WIDTH-40, box_y + box_h)], 
                               radius=15, fill=(15, 15, 18, 230), outline=accent, width=2)
                               
        def draw_portrait(fighter_name, side="left"):
            """Helper to draw B&W Duotone 3D fighter portraits"""
            if not fighter_name: return
            img_path = os.path.join(ASSETS_DIR, "images_cache", f"{fighter_name.lower().replace(' ', '_')}.png")
            if os.path.exists(img_path):
                try:
                    f_img = Image.open(img_path).convert("RGBA")
                    
                    # Apply B&W Duotone
                    gray = f_img.convert("L")
                    f_img_bw = Image.merge("RGBA", (gray, gray, gray, f_img.split()[3]))
                    
                    # Tint with theme color subtly
                    color_bg = Image.new('RGBA', f_img_bw.size, accent)
                    f_img_tinted = Image.blend(f_img_bw, color_bg, alpha=0.15)
                    f_img_tinted.putalpha(f_img.split()[3])
                    
                    # Target height increased to 200 to maintain huge 3D pop-out on taller boxes
                    target_h = 200
                    ratio = target_h / f_img.height
                    target_w = int(f_img.width * ratio)
                    f_img_resized = f_img_tinted.resize((target_w, target_h), Image.LANCZOS)
                    
                    if side == "left":
                        img_x = 25
                    else:
                        img_x = WIDTH - 25 - target_w # Anchored to the right edge
                        
                    # Bottom aligned, breaking out top
                    img_y = box_y + box_h - target_h
                    
                    # Paste using alpha mask
                    overlay.paste(f_img_resized, (img_x, img_y), f_img_resized)
                except Exception as e:
                    pass
        
        # Draw Dual Duel Portraits
        draw_portrait(f1_name, "left")
        draw_portrait(f2_name, "right")
        
        # Text Constraints (Centered Panel)
        center_x = WIDTH // 2
        max_width = 540  # Safe zone between the two portraits
        
        # TRUE GEOMETRIC SCALING (No more "...")
        def get_text_width(text, font):
            if hasattr(font, 'getlength'):
                return font.getlength(text)
            elif hasattr(draw, 'textbbox'):
                return draw.textbbox((0, 0), text, font=font)[2]
            else:
                return font.getsize(text)[0]
                
        def scale_font_to_fit(font_family, start_size, text, target_width):
            """Returns dynamically shrunk font object so text strictly fits inside target width."""
            s = start_size
            f = load_font(font_family, s)
            while get_text_width(text, f) > target_width and s > 16:
                s -= 1
                f = load_font(font_family, s)
            return f
            
        display_text = match_display.upper()
        font_pick_title_dyn = scale_font_to_fit("headline", 44, display_text, max_width)
            
        # Perfect Center Stack Alignment Calculation (Total stack height ~128px vs 160px box)
        text_y_start = box_y + 25
        
        # Layer 1: Fighter Names (MATCH) - Theme Colored, Big, Centered
        draw.text((center_x + 2, text_y_start + 2), display_text, font=font_pick_title_dyn, fill="#000000", anchor="mt")
        draw.text((center_x, text_y_start), display_text, font=font_pick_title_dyn, fill=accent, anchor="mt")
        
        # Layer 2: Pick Detail - STRICTLY PURE WHITE, Expanded gap to prevent cramming
        pick_display = pick_text.replace(' ML', ' Moneyline').replace('Fight Does NOT Go Distance / Under 2.5', 'FDGTD')
        font_pick_desc_dyn = scale_font_to_fit("regular", 26, pick_display, max_width)
            
        pick_y = text_y_start + 50 # Clean breathable gap!
        draw.text((center_x + 2, pick_y + 2), pick_display, font=font_pick_desc_dyn, fill="#000000", anchor="mt")
        draw.text((center_x, pick_y), pick_display, font=font_pick_desc_dyn, fill="#FFFFFF", anchor="mt")
        
        # Layer 3: Odds (Perfectly centered underneath string)
        odds_y = pick_y + 42 # Generous gap allowing Odds to sit naturally
        font_odds_side_dyn = scale_font_to_fit("headline", 38, odds_label, max_width)
        draw.text((center_x + 2, odds_y + 2), odds_label, font=font_odds_side_dyn, fill="#000000", anchor="mt")
        draw.text((center_x, odds_y), odds_label, font=font_odds_side_dyn, fill=accent, anchor="mt")
        
        y += 195 # MASSIVE margin between boxes to accommodate the taller box and 200px portrait bursts
    
    # ===========================================
    # PARLAY SECTION (HORIZONTAL LAYOUT)
    # ===========================================
    y += 10 # Post picks spacing
    
    draw.line([(120, y+2), (WIDTH-120, y+2)], fill="#000000", width=4)
    draw.line([(120, y), (WIDTH-120, y)], fill=accent, width=3)
    y += 40 # Standard gap
    
    num_picks = len(slip_data[:max_legs])
    draw.text((WIDTH//2 + 2, y + 2), f"--- {num_picks}-LEG PARLAY ---", font=font_subtitle, fill="#000000", anchor="mt")
    draw.text((WIDTH//2, y), f"--- {num_picks}-LEG PARLAY ---", font=font_subtitle, fill="#FFFFFF", anchor="mt")
    y += 55 # Adjusted gap
    
    # MASSIVE odds display
    draw.text((WIDTH//2 + 4, y + 4), f"@ {total_odds}", font=font_odds, fill="#000000", anchor="mt")
    draw.text((WIDTH//2, y), f"@ {total_odds}", font=font_odds, fill=accent, anchor="mt")
    y += 115 # Safe buffer to drop below the giant font
    
    # Payout (Horizontal Dual-Column Structure)
    stake_text = f"Stake:  $100"
    win_text = f"Win:  ${win_amount}"
    
    # Left column for Stake (X anchor: right-aligned from center offset)
    draw.text((WIDTH//2 - 60 + 2, y + 2), stake_text, font=font_pick_title_base, fill="#000000", anchor="rm")
    draw.text((WIDTH//2 - 60, y), stake_text, font=font_pick_title_base, fill="#FFFFFF", anchor="rm")
    
    # Right column for Win (X anchor: left-aligned from center offset)
    draw.text((WIDTH//2 + 60 + 2, y + 2), win_text, font=font_pick_title_base, fill="#000000", anchor="lm")
    draw.text((WIDTH//2 + 60, y), win_text, font=font_pick_title_base, fill=accent, anchor="lm")
    y += 60
    
    # Risk level / Edge Banner Box
    banner_y = y
    draw.rounded_rectangle([(WIDTH//2 - 160, banner_y), (WIDTH//2 + 160, banner_y + 35)], 
                           radius=8, fill=(20, 20, 20, 200), outline=accent, width=1)
    
    if slip_type == "violence":
        draw.text((WIDTH//2, banner_y + 17), "RISK: EXTREME", font=font_small, fill="#FF4444", anchor="mm")
    elif slip_type == "value":
        draw.text((WIDTH//2, banner_y + 17), "MODEL EDGE", font=font_small, fill="#FFD700", anchor="mm")
    else:
        draw.text((WIDTH//2, banner_y + 17), "CONFIDENCE: MAX", font=font_small, fill="#00FF41", anchor="mm")
    
    # ===========================================
    # FOOTER (GUARANTEED CLEARANCE ON NEW TALL CANVAS)
    # ===========================================
    barcode_y = banner_y + 60 # Safe gap below banner
    for i in range(30):
        x = 360 + i * 12
        height = 25 if i % 3 == 0 else 12
        draw.rectangle([(x, barcode_y), (x + 5, barcode_y + height)], fill=(255,255,255,60))
        
    footer_y = barcode_y + 35 # Safe gap below barcode
    draw.text((WIDTH//2, footer_y), "FIGHTIQ", font=font_subtitle, fill=accent, anchor="mt", stroke_width=3, stroke_fill="#000000")
    
    return overlay

# ===========================================
# COMPOSITE FUNCTION
# ===========================================
def create_hybrid_ticket(slip_data, slip_type):
    """
    Create ticket using Hybrid Engine:
    1. AI generates artistic background (no text)
    2. PIL renders all data (100% accurate)
    3. Composite = Perfect ticket
    """
    
    print(f"\n{'='*50}")
    print(f"🎫 {slip_type.upper()} SLIP - Hybrid Generation")
    print(f"{'='*50}")
    
    # Calculate data
    total_odds = calculate_parlay_odds(slip_data)
    win_amount = int(100 * total_odds)
    
    max_legs = getattr(config, "PARLAY_MAX_LEGS", 3) if config else 3
    print(f"   📊 {len(slip_data[:max_legs])} picks @ {total_odds} = ${win_amount}")
    
    # Step 1: Get background (AI-generated or cached)
    background = get_or_generate_background(slip_type)
    
    # Step 2: Render data layer with PIL (100% accurate text)
    print(f"   ✍️ Rendering text layer with PIL...")
    data_layer = render_data_layer(slip_data, slip_type, total_odds, win_amount)
    
    # Step 3: Composite
    print(f"   🔀 Compositing layers...")
    background = background.convert("RGBA")
    final = Image.alpha_composite(background, data_layer)
    final = final.convert("RGB")
    
    print(f"   ✅ Hybrid ticket complete!")
    return final

# ===========================================
# MAIN
# ===========================================
def main():
    print("="*60)
    print("🎫 HYBRID TICKET GENERATOR V10")
    print("   AI backgrounds + PIL text = Perfect accuracy")
    print("="*60)
    
    try:
        with open(INPUT_FILE, "r") as f:
            parlays = json.load(f)
    except:
        print(f"❌ '{INPUT_FILE}' not found.")
        return
    
    generated = []
    
    for slip_type in ["safe", "violence", "value"]:
        slip_data = parlays.get(f"{slip_type}_slip", [])
        
        if not slip_data:
            print(f"\n⚠️ No {slip_type} slip data found, skipping")
            continue
        
        # Generate with Hybrid Engine
        ticket = create_hybrid_ticket(slip_data, slip_type)
        
        # Save
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = f"{OUTPUT_DIR}/Ticket_{slip_type.capitalize()}.png"
        ticket.save(filename, "PNG", quality=95)
        
        print(f"   💾 Saved: {filename}")
        generated.append(filename)
    
    print(f"\n{'='*60}")
    print(f"✅ Generated {len(generated)} tickets with PERFECT text accuracy")
    print(f"💰 API Cost: ~${len([f for f in generated if 'cached' not in f]) * 0.04:.2f}")
    print("="*60)

if __name__ == "__main__":
    main()
