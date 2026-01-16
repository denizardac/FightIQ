import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont
import math

# ==========================================
# 🎫 FIGHTIQ: BETTING TICKET GENERATOR
# ==========================================

OUTPUT_DIR = "visuals"
PARLAY_FILE = "4_parlays.json"

# 🎨 DESIGN SYSTEM
COLORS = {
    "bg_top": "#1a1a1a",
    "bg_bottom": "#0d0d0d",
    "text_white": "#FFFFFF",
    "text_gray": "#EEEEEE",
    "text_dark": "#AAAAAA",
    "accent_safe": "#00FF41",      # Green
    "accent_violence": "#FF0055",  # Red
    "accent_value": "#00D9FF",     # Cyan
    "gold": "#FFD700",
    "separator": "#444444"
}

SLIP_CONFIG = {
    "safe": {
        "emoji": "💰",
        "title": "SAFE SLIP",
        "subtitle": "BANKO KOMBOS",
        "accent": COLORS["accent_safe"]
    },
    "violence": {
        "emoji": "🩸",
        "title": "VIOLENCE SLIP",
        "subtitle": "FINISH GUARANTEED",
        "accent": COLORS["accent_violence"]
    },
    "value": {
        "emoji": "💎",
        "title": "VALUE SLIP",
        "subtitle": "SHARP MONEY",
        "accent": COLORS["accent_value"]
    }
}

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def get_font(size, bold=False):
    """
    Attempt to load custom fonts, fallback to default if not available.
    """
    # Try multiple font paths
    font_paths = [
        # Custom fonts (if downloaded)
        f"fonts/Roboto-Bold.ttf",
        f"fonts/Arial-Bold.ttf",
        # System fonts (Windows)
        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
        "C:/Windows/Fonts/arial.ttf",     # Arial Regular
        # Fallback
        None
    ]
    
    if not bold:
        font_paths.insert(2, "C:/Windows/Fonts/arial.ttf")
    
    for font_path in font_paths:
        try:
            if font_path:
                return ImageFont.truetype(font_path, size)
        except:
            continue
    
    # Ultimate fallback: PIL default font
    return ImageFont.load_default()

def draw_gradient_background(draw, width, height, color_top, color_bottom):
    """
    Draw a vertical gradient background.
    """
    # Convert hex to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    rgb_top = hex_to_rgb(color_top)
    rgb_bottom = hex_to_rgb(color_bottom)
    
    for y in range(height):
        # Calculate blend ratio
        ratio = y / height
        r = int(rgb_top[0] * (1 - ratio) + rgb_bottom[0] * ratio)
        g = int(rgb_top[1] * (1 - ratio) + rgb_bottom[1] * ratio)
        b = int(rgb_top[2] * (1 - ratio) + rgb_bottom[2] * ratio)
        
        draw.line([(0, y), (width, y)], fill=(r, g, b))

def draw_barcode(draw, x, y, width, height):
    """
    Draw a fake aesthetic barcode for authenticity.
    """
    bar_width = 3
    spacing = 2
    num_bars = width // (bar_width + spacing)
    
    for i in range(num_bars):
        # Random-ish pattern (deterministic)
        bar_height = height if (i * 7 + 13) % 3 == 0 else height // 2
        x_pos = x + i * (bar_width + spacing)
        y_pos = y + (height - bar_height) //2
        draw.rectangle([x_pos, y_pos, x_pos + bar_width, y_pos + bar_height], fill="#FFFFFF")

def calculate_parlay_odds(picks):
    """
    Calculate combined parlay odds from individual picks.
    Placeholder logic - extract from pick string if available.
    """
    # For now, return a sample odds
    # In production, parse from pick["pick"] string or odds data
    return round(2.0 + len(picks) * 0.5, 2)

def generate_betting_ticket(slip_data, slip_type, event_name="UFC"):
    """
    Generate a professional betting ticket image.
    
    Args:
        slip_data: List of picks (from 4_parlays.json)
        slip_type: "safe", "violence", or "value"
        event_name: UFC event name
    
    Returns:
        str: Path to generated ticket image
    """
    # Dimensions (Instagram portrait optimized)
    WIDTH = 1080
    HEIGHT = 1350
    
    # Create image with gradient background
    img = Image.new('RGB', (WIDTH, HEIGHT), color=COLORS["bg_top"])
    draw = ImageDraw.Draw(img)
    
    # Draw gradient
    draw_gradient_background(draw, WIDTH, HEIGHT, COLORS["bg_top"], COLORS["bg_bottom"])
    
    # Get config for slip type
    config = SLIP_CONFIG.get(slip_type, SLIP_CONFIG["safe"])
    
    # Fonts
    font_header = get_font(72, bold=True)
    font_title = get_font(48, bold=True)
    font_picks = get_font(32)
    font_odds = get_font(36, bold=True)
    font_parlay = get_font(64, bold=True)
    font_footer = get_font(24)
    
    # Padding
    padding = 60
    y_pos = padding
    
    # === HEADER ===
    header_text = f"{config['emoji']}  FIGHTIQ ALGORITHM"
    draw.text((WIDTH // 2, y_pos), header_text, font=font_header, 
              fill=COLORS["text_white"], anchor="mt")
    y_pos += 100
    
    # === TITLE ===
    draw.text((WIDTH // 2, y_pos), config['title'], font=font_title,
              fill=config['accent'], anchor="mt")
    y_pos += 60
    
    draw.text((WIDTH // 2, y_pos), config['subtitle'], font=font_footer,
              fill=COLORS["text_dark"], anchor="mt")
    y_pos += 80
    
    # === SEPARATOR ===
    draw.line([(padding, y_pos), (WIDTH - padding, y_pos)], 
              fill=COLORS["separator"], width=2)
    y_pos += 40
    
    # === PICKS ===
    for i, pick in enumerate(slip_data):
        if i >= 5:  # Limit to 5 picks for space
            break
        
        # Pick text
        pick_text = f"✅  {pick['match']}"
        # Try to extract fighter name from match
        if " vs " in pick['match']:
            pick_text = f"✅  {pick['match'].split(' vs ')[0]}"
        
        draw.text((padding, y_pos), pick_text, font=font_picks,
                  fill=COLORS["text_gray"], anchor="lt")
        
        # Odds (if extractable from pick or reason)
        odds_text = "ML"  # Moneyline default
        draw.text((WIDTH - padding, y_pos), f"@ {odds_text}", font=font_odds,
                  fill=config['accent'], anchor="rt")
        
        y_pos += 70
    
    # === SEPARATOR ===
    y_pos += 20
    draw.line([(padding, y_pos), (WIDTH - padding, y_pos)], 
              fill=COLORS["separator"], width=3)
    y_pos += 50
    
    # === PARLAY TOTAL ===
    parlay_odds = calculate_parlay_odds(slip_data)
    
    draw.text((WIDTH // 2, y_pos), f"{len(slip_data)}-LEG PARLAY", 
              font=font_title, fill=COLORS["text_white"], anchor="mt")
    y_pos += 70
    
    draw.text((WIDTH // 2, y_pos), f"@ {parlay_odds:.2f}", 
              font=font_parlay, fill=COLORS["gold"], anchor="mt")
    y_pos += 100
    
    # === STAKE & WIN ===
    stake = 100
    potential_win = int(stake * parlay_odds)
    
    stake_win_text = f"Stake: ${stake}  →  Win: ${potential_win}"
    draw.text((WIDTH // 2, y_pos), stake_win_text,
              font=font_odds, fill=COLORS["text_gray"], anchor="mt")
    y_pos += 100
    
    # === FOOTER INFO ===
    # AI Confidence (placeholder - could extract from data)
    confidence_text = "AI Confidence: 8/10 🔥"
    draw.text((WIDTH // 2, y_pos), confidence_text,
              font=font_footer, fill=config['accent'], anchor="mt")
    y_pos += 60
    
    # === BARCODE (Aesthetic) ===
    barcode_width = 400
    barcode_height = 60
    barcode_x = (WIDTH - barcode_width) // 2
    draw_barcode(draw, barcode_x, y_pos, barcode_width, barcode_height)
    y_pos += barcode_height + 40
    
    # === BRANDING ===
    footer_text = f"fightiq.ai  |  {event_name}"
    draw.text((WIDTH // 2, y_pos), footer_text,
              font=font_footer, fill=COLORS["text_dark"], anchor="mt")
    
    # === SAVE ===
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    filename = f"{OUTPUT_DIR}/Ticket_{slip_type.capitalize()}.png"
    img.save(filename, "PNG")
    
    return filename

def main():
    print("--- 🎫 BETTING TICKET GENERATOR ---")
    
    # Load parlay data
    if not os.path.exists(PARLAY_FILE):
        print(f"❌ '{PARLAY_FILE}' not found. Run step 07 first.")
        return
    
    try:
        with open(PARLAY_FILE, "r", encoding="utf-8") as f:
            parlays = json.load(f)
    except Exception as e:
        print(f"❌ Error loading parlays: {e}")
        return
    
    # Generate tickets for each slip type
    slip_types = ["safe_slip", "violence_slip", "value_slip"]
    generated = []
    
    for slip_key in slip_types:
        slip_data = parlays.get(slip_key, [])
        
        if not slip_data:
            print(f"⚠️ No picks in '{slip_key}', skipping.")
            continue
        
        # Extract slip type name (safe_slip -> safe)
        slip_type = slip_key.replace("_slip", "")
        
        print(f"\n🎨 Generating {slip_type.upper()} ticket...")
        print(f"   Picks: {len(slip_data)}")
        
        try:
            ticket_path = generate_betting_ticket(slip_data, slip_type)
            print(f"   ✅ Saved: {ticket_path}")
            generated.append(ticket_path)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ COMPLETE: Generated {len(generated)} betting tickets.")
    print(f"📁 Files: {', '.join(generated)}")

if __name__ == "__main__":
    main()
