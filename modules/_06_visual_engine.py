import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg
import numpy as np
import os
import sys
import requests
import shutil
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR, ASSETS_DIR
try:
    from core import config
except ImportError:
    config = None

# ==========================================
# ⚙️ AYARLAR
# ==========================================
RAW_DATA_FILE = get_data_path("2_data_final.json")
AI_DATA_FILE = get_data_path("3_results.json")
OUTPUT_DIR = VISUALS_DIR
IMG_CACHE_DIR = os.path.join(ASSETS_DIR, "images_cache")

WIDTH = 1080
HEIGHT = 1350
fighter_images_cache = {}

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

# 🎨 RENK PALETİ
COLORS = {
    "bg": "#0a0a0a", "text": "#ffffff", "accent": "#00ffff",
    "f1": "#00ff41", "f1_fill": "#00ff4133",
    "f2": "#ff0055", "f2_fill": "#ff005533",
    "primary": "#00FF41",
    "secondary": "#FFD700",
    "bg_card": "#1a1a1a",
    "text_white": "#FFFFFF",
    "text_light": "#EEEEEE",
    "text_dark": "#AAAAAA",
    "grid": "#444444",
    "card_bg": "#080808",
    "bar_fill": "#FFD700",
    "bar_empty": "#222222",
    "bar_text_label": "#CCCCCC",
    "bar_text_score": "#FFFFFF",
    "record_text": "#AAAAAA"
}

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================
def clean_visuals_folder():
    if os.path.exists(OUTPUT_DIR):
        print(f"🧹 Cleaning old visuals in '{OUTPUT_DIR}/'...")
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except: pass

def load_font(font_key, size, fallback_bold=True):
    # Try custom font from config
    try:
        if config and hasattr(config, 'FONT_PATHS'):
            return ImageFont.truetype(config.FONT_PATHS.get(font_key, ""), size)
    except: pass
    
    # Try Windows system fonts
    try:
        if fallback_bold:
            return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
        else:
            return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except: pass
    
    return ImageFont.load_default()

class ImageHunter:
    def __init__(self):
        if not os.path.exists(IMG_CACHE_DIR): os.makedirs(IMG_CACHE_DIR)
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def get_fighter_image(self, name):
        safe_name = name.replace(" ", "_").lower()
        local_path = f"{IMG_CACHE_DIR}/{safe_name}.png"
        if os.path.exists(local_path): return local_path

        print(f"   🕵️‍♂️ Hunting HD Image for: {name}...")
        try:
            url_name = name.lower().replace(" ", "-").replace("'", "")
            url = f"https://www.ufc.com/athlete/{url_name}"
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200: return None

            soup = BeautifulSoup(resp.content, 'html.parser')
            img_tag = soup.find('img', class_='hero-profile__image')
            
            if img_tag and 'src' in img_tag.attrs:
                img_data = requests.get(img_tag['src'], headers=self.headers).content
                img = Image.open(BytesIO(img_data))
                img.save(local_path, "PNG")
                print("      ✅ Image Captured!")
                return local_path
            else:
                print("      ❌ No image found on profile.")
                return None
        except: return None

# ==========================================
# 1. RADAR CHART ENGINE
# ==========================================
def create_radar_chart(fight_data):
    f1, f2 = fight_data['fighters']
    stats = fight_data.get('stats', [{}, {}])
    deep_stats = fight_data.get('deep_stats', [{}, {}])
    
    def get_score(source, key, multiplier=1.0, is_percent=False):
        try:
            val = source.get(key, 0)
            if is_percent and isinstance(val, str): val = float(val.replace('%', ''))
            return min(float(val) * multiplier, 10.0)
        except: return 0.0

    categories = ['Striking\nVol', 'Grappling', 'Finisher', 'Defense', 'Exp']
    v1 = [get_score(stats[0], 'SLpM', 1.6), get_score(stats[0], 'TD_Avg', 2.0),
          (get_score(deep_stats[0], 'ko_rate') + get_score(deep_stats[0], 'sub_rate')) / 10,
          get_score(stats[0], 'Str_Def', 1.0, True) / 10, get_score(deep_stats[0], 'total_fights', 0.33)]
    v2 = [get_score(stats[1], 'SLpM', 1.6), get_score(stats[1], 'TD_Avg', 2.0),
          (get_score(deep_stats[1], 'ko_rate') + get_score(deep_stats[1], 'sub_rate')) / 10,
          get_score(stats[1], 'Str_Def', 1.0, True) / 10, get_score(deep_stats[1], 'total_fights', 0.33)]

    v1 += v1[:1]; v2 += v2[:1]
    angles = [n / 5 * 2 * np.pi for n in range(5)]; angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(COLORS['bg']); ax.set_facecolor(COLORS['bg'])
    plt.xticks(angles[:-1], categories, color='white', size=11, weight='bold')
    ax.set_rlabel_position(0); plt.yticks([2,4,6,8,10], [], color=COLORS['grid']); plt.ylim(0,10)
    ax.spines['polar'].set_color(COLORS['grid']); ax.grid(color=COLORS['grid'], linestyle='--', alpha=0.5)
    
    ax.plot(angles, v1, color=COLORS['f1'], linewidth=3, label=f1)
    ax.fill(angles, v1, color=COLORS['f1_fill'])
    ax.plot(angles, v2, color=COLORS['f2'], linewidth=3, label=f2)
    ax.fill(angles, v2, color=COLORS['f2_fill'])
    
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor='white')
    plt.title(f"{f1.upper()} VS {f2.upper()}", color='white', weight='bold', size=16, pad=30)
    
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    safe_name = f"{f1.replace(' ','_')}_vs_{f2.replace(' ','_')}.png"
    plt.savefig(f"{OUTPUT_DIR}/Radar_{safe_name}", facecolor=COLORS['bg'], dpi=120, bbox_inches='tight')
    plt.close()

# ==========================================
# 2. STAT CARD ENGINE (REDESIGNED for Phase 2)
# ==========================================
def create_stat_card(fighter_name, stats, one_liner, img_path=None, record="N/A", bg_path=None):
    """
    Creates a professional fighter stat card with brand identity.
    
    Phase 2 Redesign Features:
    - Circular fighter photo at top-center
    - Two-column stat layout
    - Brand colors and typography
    - FightIQ logo placement
    """
    # Import brand colors
    try:
        import config
        COLORS = config.BRAND_COLORS
        FONTS = config.FONT_PATHS
    except:
        # Fallback colors if config not available
        COLORS = {
            "primary": "#00FF41",
            "secondary": "#FFD700",
            "accent": "#FF0055",
            "bg_card": "#1a1a1a",
            "text_white": "#FFFFFF",
            "text_light": "#EEEEEE",
            "text_dark": "#AAAAAA"
        }
        FONTS = {
            "headline": "assets/fonts/BebasNeue-Regular.ttf",
            "body_bold": "assets/fonts/Roboto-Bold.ttf"
        }
    
    # Helper: Load fonts with fallback
    def load_font(font_key, size, fallback_bold=True):
        # Try custom font
        try:
            return ImageFont.truetype(FONTS.get(font_key, ""), size)
        except:
            pass
        
        # Try Windows system fonts
        try:
            if fallback_bold:
                return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
            else:
                return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
        except:
            pass
        
        # Ultimate fallback
        return ImageFont.load_default()
    
    # Dimensions
    WIDTH = 1080
    HEIGHT = 1350
    
    # Create image
    img = Image.new('RGB', (WIDTH, HEIGHT), color=COLORS['bg_card'])
    draw = ImageDraw.Draw(img)
    
    # === BACKGROUND: "GHOST WATERMARK" TECHNIQUE ===
    def add_noise(image, intensity=0.05):
        """Adds subtle grain/noise to the background for texture"""
        try:
            np_img = np.array(image)
            noise = np.random.randint(-255*intensity, 255*intensity, np_img.shape, dtype='int16')
            noisy_img = np.clip(np_img.astype('int16') + noise, 0, 255).astype('uint8')
            return Image.fromarray(noisy_img)
        except: return image

    # LAYER 0: Base Dark Background
    # (Already created above as 'img')
    
    # LAYER 1: "Ghost" - Fighter Image as Watermark
    if img_path and os.path.exists(img_path):
        try:
            # Load fighter image
            ghost_img = Image.open(img_path).convert("RGB")
            
            # Resize to fill canvas (preserve aspect, crop center)
            aspect = ghost_img.width / ghost_img.height
            target_aspect = WIDTH / HEIGHT
            
            if aspect > target_aspect:
                # Image is wider - fit to height
                new_height = HEIGHT
                new_width = int(HEIGHT * aspect)
            else:
                # Image is taller - fit to width
                new_width = WIDTH
                new_height = int(WIDTH / aspect)
            
            ghost_img = ghost_img.resize((new_width, new_height), Image.LANCZOS)
            
            # Center crop to canvas size
            left = (new_width - WIDTH) // 2
            top = (new_height - HEIGHT) // 2
            ghost_img = ghost_img.crop((left, top, left + WIDTH, top + HEIGHT))
            
            # Convert to grayscale
            ghost_img = ghost_img.convert("L").convert("RGB")
            
            # Apply extremely low opacity (10%)
            ghost_img = ghost_img.convert("RGBA")
            alpha = Image.new('L', (WIDTH, HEIGHT), int(255 * 0.10))  # 10% opacity
            ghost_img.putalpha(alpha)
            
            # Blend onto base
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, ghost_img)
            img = img.convert("RGB")
            
            print(f"   ✨ Ghost watermark applied")
        except Exception as e:
            print(f"   ⚠️ Ghost effect failed: {e}")
    
    # LAYER 2: Procedural Noise (on top of ghost)
    img = add_noise(img, intensity=0.08)
    
    # Re-initialize draw object (img is new object after noise)
    draw = ImageDraw.Draw(img)
    
    # === CIRCULAR FIGHTER PHOTO (Top-Center Fix) ===
    photo_diameter = 320
    photo_y_pos = 80
    
    if img_path and os.path.exists(img_path):
        try:
            fighter_img = Image.open(img_path).convert("RGB")
            
            # P0 FIX: TOP-CENTER CROP (Don't cut off head)
            # Find the square size (min dimension)
            size = min(fighter_img.size)
            
            # X: Center horizontally
            left = (fighter_img.width - size) // 2
            right = left + size
            
            # Y: Top aligned (0 to size) 
            # Note: If image is wider than tall, this is effectively center vertical too (0 to height).
            # If image is taller than wide (Portrait), this crops the TOP square (Head).
            top = 0 
            bottom = size
            
            fighter_img = fighter_img.crop((left, top, right, bottom))
            fighter_img = fighter_img.resize((photo_diameter, photo_diameter), Image.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (photo_diameter, photo_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, photo_diameter, photo_diameter), fill=255)
            
            # Create circular photo
            circular_photo = Image.new('RGBA', (photo_diameter, photo_diameter), (0, 0, 0, 0))
            circular_photo.paste(fighter_img, (0, 0))
            circular_photo.putalpha(mask)
            
            # Add glow border
            glow_diameter = photo_diameter + 12
            glow_img = Image.new('RGBA', (glow_diameter, glow_diameter), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            # Draw glow ring
            hex_to_rgb = lambda h: tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            glow_color = hex_to_rgb(COLORS['primary']) + (255,)
            glow_draw.ellipse((0, 0, glow_diameter, glow_diameter), outline=glow_color, width=6)
            
            # Paste on main image
            photo_x_pos = (WIDTH - glow_diameter) // 2
            img.paste(glow_img, (photo_x_pos, photo_y_pos - 6), glow_img)
            img.paste(circular_photo, (photo_x_pos + 6, photo_y_pos), circular_photo)
            
        except Exception as e:
            print(f"Warning: Could not load fighter image: {e}")
            img_path = None
    
    # === FIGHTER NAME (Below Photo) ===
    name_y_pos = photo_y_pos + photo_diameter + 40
    font_name = load_font("headline", 64, True)
    
    draw.text((WIDTH // 2, name_y_pos), fighter_name.upper(), 
              font=font_name, fill=COLORS['text_white'], anchor="mt")
    
    # === RECORD (Below Name) ===
    record_y_pos = name_y_pos + 80
    font_record = load_font("body_bold", 28)
    
    draw.text((WIDTH // 2, record_y_pos), f"RECORD: {record}", 
              font=font_record, fill=COLORS['text_dark'], anchor="mt")
    
    # === ONE-LINER (Tagline) ===
    tagline_y_pos = record_y_pos + 50
    font_tagline = load_font("body_bold", 32)
    
    draw.text((WIDTH // 2, tagline_y_pos), f'"{one_liner}"', 
              font=font_tagline, fill=COLORS['primary'], anchor="mt", 
              align="center")
    
    # === SEPARATOR LINE ===
    separator_y = tagline_y_pos + 60
    separator_margin = 120
    draw.line([(separator_margin, separator_y), (WIDTH - separator_margin, separator_y)],
              fill=COLORS['primary'], width=3)
    
    # === STATS (Two-Column Layout) ===
    stats_start_y = separator_y + 60
    
    # Helper: Safe integer conversion
    def safe_int(val):
        try:
            if isinstance(val, (int, float)): return int(val)
            # Remove non-numeric chars (except dot)
            clean = "".join([c for c in str(val) if c.isdigit()])
            return int(clean) if clean else 50
        except: return 50

    # Get stats
    attributes = {
        'POWER': safe_int(stats.get('power', 50)),
        'GRAPPLING': safe_int(stats.get('grappling', 50)),
        'STAMINA': safe_int(stats.get('stamina', 50)),
        'CHIN': safe_int(stats.get('chin', 50)),
        'TECHNIQUE': safe_int(stats.get('technique', 50))
    }
    
    # Two columns
    left_stats = ['POWER', 'STAMINA', 'TECHNIQUE']
    right_stats = ['GRAPPLING', 'CHIN']
    
    font_stat_label = load_font("body_bold", 24)
    font_stat_value = load_font("headline", 56, True)
    
    # Left column
    x_left = 140
    y_pos = stats_start_y
    for stat_name in left_stats:
        value = attributes[stat_name]
        
        # Label
        draw.text((x_left, y_pos), stat_name, 
                  font=font_stat_label, fill=COLORS['text_light'], anchor="lt")
        
        # Value (large number)
        draw.text((x_left, y_pos + 30), str(value), 
                  font=font_stat_value, fill=COLORS['secondary'], anchor="lt")
        
        # Progress bar
        bar_y = y_pos + 95
        bar_width = 320
        bar_height = 8
        
        # Background bar
        draw.rectangle([x_left, bar_y, x_left + bar_width, bar_y + bar_height],
                       fill='#333333')
        
        # Filled bar
        fill_width = int(bar_width * (value / 100))
        draw.rectangle([x_left, bar_y, x_left + fill_width, bar_y + bar_height],
                       fill=COLORS['primary'])
        
        y_pos += 150
    
    # Right column
    x_right = 580
    y_pos = stats_start_y
    for stat_name in right_stats:
        value = attributes[stat_name]
        
        # Label
        draw.text((x_right, y_pos), stat_name, 
                  font=font_stat_label, fill=COLORS['text_light'], anchor="lt")
        
        # Value
        draw.text((x_right, y_pos + 30), str(value), 
                  font=font_stat_value, fill=COLORS['secondary'], anchor="lt")
        
        # Progress bar
        bar_y = y_pos + 95
        bar_width = 320
        bar_height = 8
        
        draw.rectangle([x_right, bar_y, x_right + bar_width, bar_y + bar_height],
                       fill='#333333')
        
        fill_width = int(bar_width * (value / 100))
        draw.rectangle([x_right, bar_y, x_right + fill_width, bar_y + bar_height],
                       fill=COLORS['primary'])
        
        y_pos += 150
    
    # === LOGO/BRANDING (Bottom) ===
    logo_y = HEIGHT - 80
    font_logo = load_font("headline", 36, True)
    
    # Try to load logo image (if exists)
    logo_path = "assets/fightiq_logo.png"
    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((200, 60), Image.LANCZOS)
            logo_x = (WIDTH - logo_img.width) // 2
            img.paste(logo_img, (logo_x, logo_y - 30), logo_img)
        except:
            # Text fallback
            draw.text((WIDTH // 2, logo_y), "FIGHTIQ SCOUTING REPORT", 
                      font=font_logo, fill=COLORS['text_dark'], anchor="mt")
    else:
        # Text logo
        draw.text((WIDTH // 2, logo_y), "FIGHTIQ", 
                  font=font_logo, fill=COLORS['primary'], anchor="mt")
        
        font_subtitle = load_font("body_bold", 18)
        draw.text((WIDTH // 2, logo_y + 45), "SCOUTING REPORT", 
                  font=font_subtitle, fill=COLORS['text_dark'], anchor="mt")
    
    # === SAVE ===
    safe_name = fighter_name.replace(" ", "_")
    filename = f"{OUTPUT_DIR}/Card_{safe_name}.png"
    img.save(filename, "PNG")
    print(f"   ✅ Created: {filename}")

# ==========================================
# 3. VERSUS CARD ENGINE (Oracle Mode)
# ==========================================
def create_versus_card(fighter1_data, fighter2_data, card_stats):
    """
    Creates a high-quality split-screen Versus Card for two fighters.
    card_stats must be: {'fighter1': {power, grappling, ...}, 'fighter2': {power, grappling, ...}}
    OR a direct single-fighter dict (legacy fallback).
    """
    f1_name = fighter1_data['name']
    f2_name = fighter2_data['name']
    print(f"    Creating Versus Card: {f1_name} vs {f2_name}...")

    hunter = ImageHunter()
    path1 = hunter.get_fighter_image(f1_name)
    path2 = hunter.get_fighter_image(f2_name)

    # ── 1. Background ─────────────────────────────────────
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(8, 8, 8))

    # Subtle gradient: left green tint, right cyan tint
    try:
        overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for x in range(WIDTH // 2):
            alpha = int(30 * (1 - x / (WIDTH // 2)))
            ov_draw.line([(x, 0), (x, HEIGHT)], fill=(0, 255, 65, alpha))
        for x in range(WIDTH // 2, WIDTH):
            alpha = int(30 * ((x - WIDTH // 2) / (WIDTH // 2)))
            ov_draw.line([(x, 0), (x, HEIGHT)], fill=(0, 255, 255, alpha))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    except Exception:
        pass

    # Subtle noise
    try:
        np_img = np.array(img)
        noise = np.random.randint(-12, 12, np_img.shape, dtype='int16')
        img = Image.fromarray(np.clip(np_img.astype('int16') + noise, 0, 255).astype('uint8'))
    except Exception:
        pass

    draw = ImageDraw.Draw(img)

    # ── 2. Ghost background images ────────────────────────
    def draw_ghost(img_path, is_left):
        if not img_path or not os.path.exists(img_path):
            return
        try:
            ghost = Image.open(img_path).convert("RGBA")
            ghost = ImageOps.grayscale(ghost).convert("RGBA")
            g_size = int(HEIGHT * 0.75)
            ghost = ghost.resize((g_size, g_size), Image.LANCZOS)
            pixels = ghost.getdata()
            ghost.putdata([(p[0], p[1], p[2], int(p[3] * 0.08)) for p in pixels])
            x_off = -int(g_size * 0.15) if is_left else WIDTH - int(g_size * 0.85)
            img.paste(ghost, (x_off, HEIGHT - g_size - 50), ghost)
        except Exception:
            pass

    draw_ghost(path1, True)
    draw_ghost(path2, False)
    draw = ImageDraw.Draw(img)

    # ── 3. Vertical center divider ────────────────────────
    center_x = WIDTH // 2
    for i in range(3):
        alpha = [40, 100, 40][i]
        x = center_x + (i - 1)
        draw.line([(x, 80), (x, HEIGHT - 80)], fill=(255, 215, 0, alpha))

    # ── 4. TOP BANNER ─────────────────────────────────────
    w1 = fighter1_data.get('weight_class', '').replace("Women's ", "").strip()
    w2 = fighter2_data.get('weight_class', '').replace("Women's ", "").strip()
    if w1 == w2 and w1:
        banner_text = f"{w1.upper()} BOUT  ·  FIGHTIQ ANALYSIS"
    else:
        banner_text = "FIGHTIQ  ·  MATCHUP ANALYSIS"

    font_banner = load_font("headline", 34)
    banner_h = 64
    draw.rectangle([(0, 0), (WIDTH, banner_h)], fill=(15, 15, 15))
    draw.text((WIDTH // 2, banner_h // 2), banner_text, font=font_banner,
              fill=COLORS['secondary'], anchor="mm")
    draw.line([(0, banner_h), (WIDTH, banner_h)], fill=COLORS['secondary'], width=2)

    # ── 5. Fighter photos (circles) ───────────────────────
    photo_diameter = 360
    photo_y = 80
    glow_pad = 14

    def paste_fighter_circle(img_path, x_center, glow_color_hex):
        fallback = os.path.join(ASSETS_DIR, "silhouette.png")
        src = img_path if (img_path and os.path.exists(img_path)) else fallback
        if not (src and os.path.exists(src)):
            return
        try:
            raw = Image.open(src).convert("RGBA")
            rw, rh = raw.size
            # Scale to fill circle while keeping aspect ratio (crop from center)
            scale = max(photo_diameter / rw, photo_diameter / rh)
            new_w = int(rw * scale)
            new_h = int(rh * scale)
            raw = raw.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - photo_diameter) // 2
            top = max(0, (new_h - photo_diameter) // 4)  # bias toward top (face)
            top = min(top, new_h - photo_diameter)
            cropped = raw.crop((left, top, left + photo_diameter, top + photo_diameter))

            # Circular mask
            mask = Image.new('L', (photo_diameter, photo_diameter), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, photo_diameter, photo_diameter), fill=255)
            cropped.putalpha(mask)

            # Glow ring
            gd = photo_diameter + glow_pad * 2
            glow = Image.new('RGBA', (gd, gd), (0, 0, 0, 0))
            gd_draw = ImageDraw.Draw(glow)
            hex_rgb = tuple(int(glow_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            for thickness, alpha in [(10, 60), (7, 120), (4, 200), (2, 255)]:
                gd_draw.ellipse((0, 0, gd - 1, gd - 1), outline=hex_rgb + (alpha,), width=thickness)

            gx = x_center - gd // 2
            gy = photo_y
            img.paste(glow, (gx, gy), glow)
            img.paste(cropped, (gx + glow_pad, gy + glow_pad), cropped)
        except Exception as e:
            print(f"      Photo error ({src}): {e}")

    paste_fighter_circle(path1, WIDTH // 4, COLORS['primary'])
    paste_fighter_circle(path2, 3 * WIDTH // 4, COLORS['accent'])
    draw = ImageDraw.Draw(img)

    # ── 6. Names & Records ────────────────────────────────
    name_y = photo_y + photo_diameter + glow_pad * 2 + 18
    font_name = load_font("headline", 56)
    font_record = load_font("body_bold", 24)
    font_nickname = load_font("body_bold", 20)

    def truncate_name(name, max_chars=14):
        parts = name.upper().split()
        if len(' '.join(parts)) <= max_chars:
            return ' '.join(parts)
        return parts[-1] if parts else name.upper()

    def format_record(record_str):
        """Show 'DEBUT' for 0-0-0, otherwise show W-L-D."""
        if not record_str or record_str == 'N/A':
            return 'N/A'
        parts = record_str.split('-')
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            if int(parts[0]) == 0 and int(parts[1]) == 0:
                return 'UFC DEBUT'
        return record_str

    def truncate_oneliner(text, max_chars=32):
        """Trim one-liner to fit on card without overflow."""
        if not text:
            return ''
        if len(text) <= max_chars:
            return text
        # Try to cut at last space before limit
        cut = text[:max_chars].rsplit(' ', 1)[0]
        return cut + '…'

    # Left fighter
    draw.text((WIDTH // 4, name_y), truncate_name(f1_name),
              font=font_name, fill=COLORS['primary'], anchor="mt")
    rec1 = format_record(fighter1_data.get('record', 'N/A'))
    draw.text((WIDTH // 4, name_y + 62), rec1,
              font=font_record, fill=(200, 200, 200), anchor="mt")
    ol1 = truncate_oneliner(fighter1_data.get('one_liner', ''))
    if ol1:
        draw.text((WIDTH // 4, name_y + 90), f'"{ol1}"',
                  font=font_nickname, fill=(140, 140, 140), anchor="mt")

    # Right fighter
    draw.text((3 * WIDTH // 4, name_y), truncate_name(f2_name),
              font=font_name, fill=COLORS['accent'], anchor="mt")
    rec2 = format_record(fighter2_data.get('record', 'N/A'))
    draw.text((3 * WIDTH // 4, name_y + 62), rec2,
              font=font_record, fill=(200, 200, 200), anchor="mt")
    ol2 = truncate_oneliner(fighter2_data.get('one_liner', ''))
    if ol2:
        draw.text((3 * WIDTH // 4, name_y + 90), f'"{ol2}"',
                  font=font_nickname, fill=(140, 140, 140), anchor="mt")

    # ── 7. VS Badge ───────────────────────────────────────
    vs_y = name_y + 30
    vs_dia = 110
    vs_cx = center_x
    vs_bg = Image.new('RGBA', (vs_dia, vs_dia), (0, 0, 0, 0))
    vs_bg_draw = ImageDraw.Draw(vs_bg)
    vs_bg_draw.ellipse((0, 0, vs_dia, vs_dia), fill=(255, 215, 0, 230))
    vs_bg_draw.ellipse((0, 0, vs_dia, vs_dia), outline=(255, 255, 255, 180), width=3)
    img.paste(vs_bg, (vs_cx - vs_dia // 2, vs_y - vs_dia // 2), vs_bg)
    draw = ImageDraw.Draw(img)
    font_vs = load_font("headline", 64)
    draw.text((vs_cx, vs_y), "VS", font=font_vs, fill=(10, 10, 10), anchor="mm")

    # ── 8. Tale of the Tape ───────────────────────────────
    tape_y = vs_y + vs_dia // 2 + 22
    font_tape = load_font("body_bold", 19)
    font_tape_lbl = load_font("body_bold", 15)

    tape_fields = [
        ("HEIGHT", fighter1_data.get('height', '--'), fighter2_data.get('height', '--')),
        ("REACH",  fighter1_data.get('reach', '--'),  fighter2_data.get('reach', '--')),
        ("STANCE", fighter1_data.get('stance', '--'),  fighter2_data.get('stance', '--')),
        ("AGE",    str(fighter1_data.get('age', '--')),str(fighter2_data.get('age', '--'))),
    ]
    for i, (lbl, v1, v2) in enumerate(tape_fields):
        ty = tape_y + i * 30
        draw.text((center_x, ty), lbl, font=font_tape_lbl, fill="#666666", anchor="mm")
        draw.text((center_x - 90, ty), str(v1), font=font_tape, fill="#cccccc", anchor="rm")
        draw.text((center_x + 90, ty), str(v2), font=font_tape, fill="#cccccc", anchor="lm")

    # ── 9. Divider before stats ───────────────────────────
    stats_section_y = tape_y + len(tape_fields) * 30 + 24
    draw.line([(40, stats_section_y), (WIDTH - 40, stats_section_y)], fill="#333333", width=1)

    # ── 10. Attribute Bars ────────────────────────────────
    def get_stat(d, k):
        v = d.get(k, 70)
        if isinstance(v, str):
            clean = "".join(c for c in v if c.isdigit())
            return int(clean) if clean else 70
        return int(v) if v else 70

    # Resolve stats for both fighters
    stats1 = card_stats.get('fighter1', {})
    stats2 = card_stats.get('fighter2', {})
    if not stats1:
        # Legacy: card_stats might be keyed by fighter name
        stats1 = card_stats.get(f1_name, card_stats)
        stats2 = card_stats.get(f2_name, {})
    if not stats2:
        stats2 = {}

    stat_defs = [
        ('POWER',     'power'),
        ('STRIKING',  'technique'),
        ('GRAPPLING', 'grappling'),
        ('STAMINA',   'stamina'),
        ('CHIN',      'chin'),
    ]

    bar_y = stats_section_y + 28
    bar_h = 22
    bar_spacing = 58
    font_stat_lbl = load_font("body_bold", 20)
    font_stat_val = load_font("headline", 40)

    # Layout constants (fixed, tested for 1080px width)
    MARGIN = 28
    LABEL_W = 120     # Label column width
    VALUE_W = 52      # Value text width budget
    GAP = 10
    # Left:  MARGIN → label → GAP → bar → GAP → value → (to center)
    # Right: (from center) → value → GAP → bar → GAP → label → MARGIN
    bar_max_w = center_x - MARGIN - LABEL_W - GAP - VALUE_W - GAP - 12
    # bar_max_w ≈ 540 - 28 - 120 - 10 - 52 - 10 - 12 = 308

    bar_L_start = MARGIN + LABEL_W + GAP
    bar_L_end   = bar_L_start + bar_max_w
    val_L_x     = bar_L_end + GAP        # left edge of value text

    bar_R_end   = WIDTH - MARGIN - LABEL_W - GAP
    bar_R_start = bar_R_end - bar_max_w
    val_R_x     = bar_R_start - GAP      # right edge of value text (anchor rm)

    for idx, (lbl, key) in enumerate(stat_defs):
        y = bar_y + idx * bar_spacing
        v1 = get_stat(stats1, key)
        v2 = get_stat(stats2, key) if stats2 else v1

        # ─ Left fighter ─
        draw.text((MARGIN, y), lbl, font=font_stat_lbl,
                  fill="#BBBBBB", anchor="lm")
        # Bar background
        draw.rectangle([bar_L_start, y - bar_h // 2, bar_L_end, y + bar_h // 2],
                       fill="#1e1e1e")
        draw.rectangle([bar_L_start, y - bar_h // 2, bar_L_end, y + bar_h // 2],
                       outline="#333333", width=1)
        # Bar fill
        fill_w1 = int(bar_max_w * v1 / 100)
        if fill_w1 > 0:
            draw.rectangle([bar_L_start, y - bar_h // 2,
                            bar_L_start + fill_w1, y + bar_h // 2],
                           fill=COLORS['primary'])
        # Value (right of bar, green)
        draw.text((val_L_x, y), str(v1), font=font_stat_val,
                  fill=COLORS['primary'], anchor="lm")

        # ─ Right fighter ─
        draw.text((WIDTH - MARGIN, y), lbl, font=font_stat_lbl,
                  fill="#BBBBBB", anchor="rm")
        # Bar background
        draw.rectangle([bar_R_start, y - bar_h // 2, bar_R_end, y + bar_h // 2],
                       fill="#1e1e1e")
        draw.rectangle([bar_R_start, y - bar_h // 2, bar_R_end, y + bar_h // 2],
                       outline="#333333", width=1)
        # Bar fill (grows from right → left)
        fill_w2 = int(bar_max_w * v2 / 100)
        if fill_w2 > 0:
            draw.rectangle([bar_R_end - fill_w2, y - bar_h // 2,
                            bar_R_end, y + bar_h // 2],
                           fill=COLORS['accent'])
        # Value (left of bar, cyan) — drawn LAST so it is on top
        draw.text((val_R_x, y), str(v2), font=font_stat_val,
                  fill=COLORS['accent'], anchor="rm")

    # ── 11. Footer ────────────────────────────────────────
    footer_y = HEIGHT - 44
    draw.rectangle([(0, footer_y - 10), (WIDTH, HEIGHT)], fill=(12, 12, 12))
    font_footer = load_font("body_bold", 17)
    draw.text((WIDTH // 2, footer_y + 10), "FIGHTIQ.AI  ·  @FightIQBot",
              font=font_footer, fill="#444444", anchor="mm")

    # ── 12. Save ──────────────────────────────────────────
    safe1 = f1_name.replace(' ', '_').replace("'", '')
    safe2 = f2_name.replace(' ', '_').replace("'", '')
    out_path = os.path.join(VISUALS_DIR, f"Versus_{safe1}_vs_{safe2}.png")
    img.save(out_path, quality=95)
    print(f"   Versus Card saved: {out_path}")
    return out_path

def main():
    print("--- 🎨 STEP 6: VISUAL ENGINE (DESIGN & CLEAN) ---")
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    clean_visuals_folder()
    hunter = ImageHunter()

    # 1. RADARLARI OLUŞTUR
    try:
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f: raw_data = json.load(f)
        for fight in raw_data:
            if 'deep_stats' in fight: create_radar_chart(fight)
    except: pass

    # 2. STAT KARTLARI (Canlı Mod İçin)
    try:
        # Build record lookup from deep_stats (wins/losses)
        record_lookup = {}
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f: raw_data = json.load(f)
        for fight in raw_data:
            deep = fight.get('deep_stats', [])
            for ds in deep:
                if not isinstance(ds, dict): continue
                name = ds.get('name', '')
                wins = ds.get('wins', 0) or 0
                losses = ds.get('losses', 0) or 0
                draws = ds.get('draws', 0) or 0
                if name and (wins or losses):
                    record_lookup[name.lower()] = f"{wins}-{losses}-{draws}"

        with open(AI_DATA_FILE, "r", encoding="utf-8") as f: ai_data = json.load(f)
        for item in ai_data:
            brain = item.get('fight_brain_output', {})
            spotlight = brain.get('spotlight_stats', {})
            if spotlight:
                for fname, stats in spotlight.items():
                    img_path = hunter.get_fighter_image(fname)
                    record = record_lookup.get(fname.lower(), "N/A")
                    create_stat_card(fname, stats, stats.get('one_liner', ''), img_path, record=record)
    except Exception as e:
        print(f"⚠️ Stat card error: {e}")

    # 3. VERSUS KARTLARI (Her dövüş için)
    try:
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        with open(AI_DATA_FILE, "r", encoding="utf-8") as f:
            ai_data = json.load(f)

        # Build AI spotlight lookup: fighter_name → stats
        spotlight_lookup = {}
        for item in ai_data:
            brain = item.get('fight_brain_output', {})
            sp = brain.get('spotlight_stats', {})
            for fname, fstats in sp.items():
                spotlight_lookup[fname.lower()] = fstats

        for fight in raw_data:
            fighters = fight.get('fighters', [])
            if len(fighters) < 2:
                continue
            f1_name, f2_name = fighters[0], fighters[1]
            stats_list = fight.get('stats', [{}, {}])
            deep_list  = fight.get('deep_stats', [{}, {}])

            def build_fighter_data(name, stats_raw, deep_raw):
                ds = deep_raw if isinstance(deep_raw, dict) else {}
                st = stats_raw if isinstance(stats_raw, dict) else {}
                wins   = ds.get('wins', 0) or 0
                losses = ds.get('losses', 0) or 0
                draws  = ds.get('draws', 0) or 0
                # Always build W-L-D; format_record will convert 0-0-0 → UFC DEBUT
                rec = f"{wins}-{losses}-{draws}"
                sp_stats = spotlight_lookup.get(name.lower(), {})
                return {
                    'name':         name,
                    'record':       rec,
                    'weight_class': st.get('weight_class', ds.get('weight_class', '')),
                    'height':       ds.get('height', st.get('height', '--')),
                    'reach':        ds.get('reach',  st.get('reach',  '--')),
                    'stance':       ds.get('stance', st.get('stance', '--')),
                    'age':          ds.get('age',    st.get('age',    '--')),
                    'one_liner':    sp_stats.get('one_liner', ''),
                }

            f1_data = build_fighter_data(f1_name,
                                         stats_list[0] if len(stats_list) > 0 else {},
                                         deep_list[0]  if len(deep_list)  > 0 else {})
            f2_data = build_fighter_data(f2_name,
                                         stats_list[1] if len(stats_list) > 1 else {},
                                         deep_list[1]  if len(deep_list)  > 1 else {})

            sp1 = spotlight_lookup.get(f1_name.lower(), {})
            sp2 = spotlight_lookup.get(f2_name.lower(), {})
            # Provide default scores if AI hasn't generated them yet
            default_scores = {'power': 72, 'grappling': 68, 'stamina': 75, 'chin': 70, 'technique': 72}
            card_stats = {
                'fighter1': sp1 if sp1 else default_scores.copy(),
                'fighter2': sp2 if sp2 else default_scores.copy(),
            }
            try:
                create_versus_card(f1_data, f2_data, card_stats)
            except Exception as ve:
                print(f"   Versus card error ({f1_name} vs {f2_name}): {ve}")
    except Exception as e:
        print(f"⚠️ Versus card generation error: {e}")

    print(f"\n✅ VISUALS COMPLETE.")

if __name__ == "__main__":
    main()