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
from PIL import Image
from io import BytesIO

# ==========================================
# ⚙️ AYARLAR
# ==========================================
RAW_DATA_FILE = "2_data_final.json"
AI_DATA_FILE = "3_results.json"
OUTPUT_DIR = "visuals"
IMG_CACHE_DIR = "images_cache"

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

# 🎨 RENK PALETİ
COLORS = {
    "bg": "#0a0a0a", "text": "#ffffff", "accent": "#00ffff",
    "f1": "#00ff41", "f1_fill": "#00ff4133",
    "f2": "#ff0055", "f2_fill": "#ff005533",
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
            "headline": "fonts/BebasNeue-Regular.ttf",
            "body_bold": "fonts/Roboto-Bold.ttf"
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
    
    # === BACKGROUND (Nano Banana Integration) ===
    if bg_path and os.path.exists(bg_path):
        try:
            # Load AI-generated background
            bg_img = Image.open(bg_path).convert("RGB")
            
            # Resize to card dimensions
            bg_img = bg_img.resize((WIDTH, HEIGHT), Image.LANCZOS)
            
            # Apply semi-transparent overlay to not overpower content
            bg_img = bg_img.convert("RGBA")
            overlay = Image.new('RGBA', (WIDTH, HEIGHT), COLORS['bg_card'] + (180,))  # 70% opacity
            bg_img = Image.alpha_composite(bg_img, overlay)
            
            # Paste background
            img.paste(bg_img.convert("RGB"), (0, 0))
            
            print(f"   ✨ Using custom background: {bg_path}")
        except Exception as e:
            print(f"   ⚠️ Could not load custom background: {e}")
    else:
        # Try to auto-detect background based on fighter name
        if fighter_name:
            safe_name = "".join([c for c in fighter_name if c.isalnum() or c in " -_"]).replace(" ", "_")
            auto_bg_path = f"assets/backgrounds/{safe_name}.png"
            
            if os.path.exists(auto_bg_path):
                try:
                    bg_img = Image.open(auto_bg_path).convert("RGB")
                    bg_img = bg_img.resize((WIDTH, HEIGHT), Image.LANCZOS)
                    bg_img = bg_img.convert("RGBA")
                    overlay = Image.new('RGBA', (WIDTH, HEIGHT), COLORS['bg_card'] + (180,))
                    bg_img = Image.alpha_composite(bg_img, overlay)
                    img.paste(bg_img.convert("RGB"), (0, 0))
                    print(f"   ✨ Auto-detected custom background for {fighter_name}")
                except:
                    pass
    
    # === CIRCULAR FIGHTER PHOTO (Top-Center) ===
    photo_diameter = 320
    photo_y_pos = 80
    
    if img_path and os.path.exists(img_path):
        try:
            fighter_img = Image.open(img_path).convert("RGB")
            
            # Resize to square
            size = min(fighter_img.size)
            fighter_img = fighter_img.crop((
                (fighter_img.width - size) // 2,
                (fighter_img.height - size) // 2,
                (fighter_img.width + size) // 2,
                (fighter_img.height + size) // 2
            ))
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
    
    # Get stats
    attributes = {
        'POWER': stats.get('power', 50),
        'GRAPPLING': stats.get('grappling', 50),
        'STAMINA': stats.get('stamina', 50),
        'CHIN': stats.get('chin', 50),
        'TECHNIQUE': stats.get('technique', 50)
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
        with open(AI_DATA_FILE, "r", encoding="utf-8") as f: ai_data = json.load(f)
        for item in ai_data:
            brain = item.get('fight_brain_output', {})
            spotlight = brain.get('spotlight_stats', {})
            if spotlight:
                for fname, stats in spotlight.items():
                    img_path = hunter.get_fighter_image(fname)
                    create_stat_card(fname, stats, stats.get('one_liner', ''), img_path, record="N/A")
    except: pass

    print(f"\n✅ VISUALS COMPLETE.")

if __name__ == "__main__":
    main()