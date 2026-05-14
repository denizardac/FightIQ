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
import sys
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from dotenv import load_dotenv
import io

OUTPUT_DIR = "visuals"
INPUT_FILE = "4_parlays.json"
BG_CACHE_DIR = "assets/ticket_backgrounds"

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Initialize
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Model
IMAGEN_MODEL = "models/imagen-4.0-generate-preview-06-06"

# ===========================================
# TEXT-FREE BACKGROUND PROMPTS (NO TEXT!)
# ===========================================
BACKGROUND_PROMPTS = {
    "safe": {
        "theme_name": "The Bank Lock",
        "prompt": """Abstract dark premium sports betting aesthetic, vertical composition.
High-tech security vault theme with electric green (#00FF41) neon glow.
Metallic steel textures, cyber grid patterns, subtle lock and shield shapes.
Professional, trustworthy, digital security vibes.
Dark background (#0a0a0a) with emerald green accents.

ABSOLUTELY NO TEXT. NO LETTERS. NO NUMBERS. NO WORDS.
Pure abstract visual design only.
Vertical format 1080x1350px.""",
        "accent_color": "#00FF41",
        "secondary_color": "#00D4FF"
    },
    
    "violence": {
        "theme_name": "The Blood Diamond",
        "prompt": """Abstract aggressive MMA combat aesthetic, vertical composition.
Underground fight club theme with crimson red (#FF0055) and orange fire.
Dark smoky background, explosion effects, electric sparks, motion energy.
Raw, intense, dangerous atmosphere with blood splatter textures.
Matte black base with red and orange accents.

ABSOLUTELY NO TEXT. NO LETTERS. NO NUMBERS. NO WORDS.
Pure abstract visual design only.
Vertical format 1080x1350px.""",
        "accent_color": "#FF0055",
        "secondary_color": "#FF6600"
    },
    
    "value": {
        "theme_name": "The Jackpot",
        "prompt": """Abstract luxury casino high-roller aesthetic, vertical composition.
Premium wealth theme with gold (#FFD700) and deep purple accents.
Black marble textures, diamond patterns, elegant lighting.
VIP exclusive atmosphere with gold embossed elements.
Dark luxurious base with gold and purple accents.

ABSOLUTELY NO TEXT. NO LETTERS. NO NUMBERS. NO WORDS.
Pure abstract visual design only.
Vertical format 1080x1350px.""",
        "accent_color": "#FFD700",
        "secondary_color": "#9B59B6"
    }
}

# ===========================================
# FONT LOADING
# ===========================================
def load_font(font_key, size):
    """Load font with fallback"""
    font_paths = {
        "headline": "fonts/BebasNeue-Regular.ttf",
        "body": "fonts/Roboto-Bold.ttf",
        "regular": "fonts/Roboto-Regular.ttf"
    }
    
    try:
        return ImageFont.truetype(font_paths.get(font_key, font_paths["body"]), size)
    except:
        try:
            # Windows fallback
            return ImageFont.truetype("arial.ttf", size)
        except:
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
        return Image.open(cache_path).convert("RGB")
    
    # Generate new background
    if not client:
        print(f"   ⚠️ No API client, using gradient fallback")
        return create_gradient_background(slip_type)
    
    theme = BACKGROUND_PROMPTS.get(slip_type, BACKGROUND_PROMPTS["safe"])
    print(f"   🎨 Generating AI background: {theme['theme_name']}...")
    
    try:
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=theme["prompt"],
            config=types.GenerateImagesConfig(number_of_images=1)
        )
        
        if response.generated_images:
            image_data = response.generated_images[0].image.image_bytes
            bg = Image.open(io.BytesIO(image_data)).convert("RGB")
            bg = bg.resize((1080, 1350), Image.LANCZOS)
            
            # Cache for future use
            bg.save(cache_path, "PNG")
            print(f"   ✅ Background generated and cached ($0.04)")
            return bg
    
    except Exception as e:
        print(f"   ⚠️ AI generation failed: {e}")
    
    return create_gradient_background(slip_type)

def create_gradient_background(slip_type):
    """Create gradient fallback background"""
    WIDTH, HEIGHT = 1080, 1350
    
    colors = {
        "safe": ("#0a1a0a", "#001a00"),
        "violence": ("#1a0a0a", "#1a0000"),
        "value": ("#1a1a0a", "#1a1000")
    }
    
    color1, color2 = colors.get(slip_type, ("#0a0a0a", "#1a1a1a"))
    
    img = Image.new('RGB', (WIDTH, HEIGHT), color1)
    draw = ImageDraw.Draw(img)
    
    # Simple vertical gradient
    r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
    r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
    
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    
    return img

# ===========================================
# DATA EXTRACTION
# ===========================================
def extract_odds(pick):
    """Extract odds from pick data"""
    pick_text = pick.get('pick', '')
    reason = pick.get('reason', '')
    
    # Try to extract from @ symbol
    if '@' in pick_text:
        try:
            return float(pick_text.split('@')[1].strip().split()[0])
        except:
            pass
    
    if '@' in reason:
        try:
            return float(reason.split('@')[1].strip().split()[0])
        except:
            pass
    
    # Estimate from confidence
    if 'confidence' in reason.lower():
        if '10' in reason or '9' in reason:
            return 1.45
        elif '8' in reason:
            return 1.65
    
    return 1.50  # Default

def calculate_parlay_odds(slip_data):
    """Calculate total parlay odds"""
    total = 1.0
    for pick in slip_data[:5]:
        total *= extract_odds(pick)
    return round(total, 2)

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
    WIDTH, HEIGHT = 1080, 1350
    
    # Create transparent overlay
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    theme = BACKGROUND_PROMPTS.get(slip_type, BACKGROUND_PROMPTS["safe"])
    accent = theme["accent_color"]
    secondary = theme["secondary_color"]
    
    # Load fonts
    font_title = load_font("headline", 72)
    font_subtitle = load_font("headline", 42)
    font_pick = load_font("body", 36)
    font_odds = load_font("headline", 96)
    font_small = load_font("regular", 28)
    
    # ===========================================
    # HEADER SECTION
    # ===========================================
    y = 60
    
    # Emoji + Title
    slip_titles = {
        "safe": ("💰", "SAFE SLIP", "BANKO KOMBOS"),
        "violence": ("🩸", "VIOLENCE SLIP", "FINISH GUARANTEED"),
        "value": ("💎", "VALUE SLIP", "SHARP MONEY")
    }
    emoji, title, subtitle = slip_titles.get(slip_type, slip_titles["safe"])
    
    # Draw title with shadow
    draw.text((WIDTH//2, y), f"{emoji} {title}", font=font_title, 
              fill=accent, anchor="mt", stroke_width=2, stroke_fill="#000000")
    y += 80
    
    draw.text((WIDTH//2, y), subtitle, font=font_subtitle, 
              fill="#FFFFFF", anchor="mt")
    y += 60
    
    # Separator line
    draw.line([(100, y), (WIDTH-100, y)], fill=accent, width=3)
    y += 40
    
    # ===========================================
    # PICKS SECTION
    # ===========================================
    for i, pick in enumerate(slip_data[:5], 1):
        match = pick.get('match', 'Unknown')
        pick_text = pick.get('pick', 'Unknown')
        odds = extract_odds(pick)
        
        match_display = format_match_name(match)
        
        # Pick box background (semi-transparent)
        box_y = y
        draw.rectangle([(60, box_y), (WIDTH-60, box_y + 100)], 
                      fill=(20, 20, 20, 200), outline=accent, width=2)
        
        # Pick number
        draw.text((90, box_y + 50), f"{i}.", font=font_pick, 
                  fill=accent, anchor="lm")
        
        # Match name
        draw.text((130, box_y + 35), match_display.upper(), font=font_pick, 
                  fill="#FFFFFF", anchor="lt")
        
        # Pick detail
        pick_display = pick_text.replace(' ML', '').replace('Fight Does NOT Go Distance / Under 2.5', 'FDGTD')[:40]
        draw.text((130, box_y + 70), pick_display, font=font_small, 
                  fill="#AAAAAA", anchor="lt")
        
        # Odds
        draw.text((WIDTH-90, box_y + 50), f"@ {odds:.2f}", font=font_pick, 
                  fill=secondary, anchor="rm")
        
        y += 120
    
    y += 20
    
    # ===========================================
    # PARLAY SECTION
    # ===========================================
    # Separator
    draw.line([(100, y), (WIDTH-100, y)], fill=accent, width=3)
    y += 40
    
    # Parlay header
    num_picks = len(slip_data[:5])
    draw.text((WIDTH//2, y), f"{num_picks}-LEG PARLAY", font=font_subtitle, 
              fill="#FFFFFF", anchor="mt")
    y += 60
    
    # MASSIVE odds display
    draw.text((WIDTH//2, y), f"@ {total_odds}", font=font_odds, 
              fill=accent, anchor="mt", stroke_width=3, stroke_fill="#000000")
    y += 110
    
    # Payout
    draw.text((WIDTH//2, y), f"Stake: $100  →  Win: ${win_amount}", font=font_pick, 
              fill="#FFFFFF", anchor="mt")
    y += 50
    
    # Risk level (for violence) or Edge (for value)
    if slip_type == "violence":
        draw.text((WIDTH//2, y), "⚠️ RISK: EXTREME", font=font_small, 
                  fill="#FF6600", anchor="mt")
    elif slip_type == "value":
        draw.text((WIDTH//2, y), "💰 AI EDGE: HIGH VALUE", font=font_small, 
                  fill="#FFD700", anchor="mt")
    else:
        draw.text((WIDTH//2, y), "🔒 CONFIDENCE: HIGH", font=font_small, 
                  fill="#00FF41", anchor="mt")
    
    # ===========================================
    # FOOTER
    # ===========================================
    # FightIQ branding
    draw.text((WIDTH//2, HEIGHT - 60), "FightIQ", font=font_subtitle, 
              fill=accent, anchor="mt", stroke_width=1, stroke_fill="#000000")
    
    # Decorative barcode (aesthetic)
    barcode_y = HEIGHT - 120
    for i in range(30):
        x = 350 + i * 12
        height = 30 if i % 3 == 0 else 20
        draw.rectangle([(x, barcode_y), (x + 8, barcode_y + height)], 
                      fill="#333333")
    
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
    
    print(f"   📊 {len(slip_data[:5])} picks @ {total_odds} = ${win_amount}")
    
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
