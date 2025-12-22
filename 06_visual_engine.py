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
# 2. STAT CARD ENGINE
# ==========================================
def create_stat_card(fighter_name, stats, one_liner, img_path=None, record="N/A"):
    fig, ax = plt.subplots(figsize=(7, 9)) 
    fig.patch.set_facecolor(COLORS['card_bg']); ax.set_facecolor(COLORS['card_bg']); ax.axis('off')

    # --- FOTOĞRAF YERLEŞTİRME ---
    if img_path:
        try:
            img = mpimg.imread(img_path)
            new_ax = fig.add_axes([0.40, 0.05, 0.60, 0.60], anchor='SE', zorder=1)
            new_ax.imshow(img); new_ax.axis('off')
            text_x_align, bar_start_x, bar_width = 0.05, 0.05, 0.45
            header_align, header_x = 'left', 0.05
        except: img_path = None
    
    if not img_path:
        text_x_align, bar_start_x, bar_width = 0.15, 0.15, 0.7
        header_align, header_x = 'center', 0.5

    # --- BAŞLIK VE REKOR ---
    plt.text(header_x, 0.94, fighter_name.upper(), ha=header_align, va='center', 
             color=COLORS['text'], fontsize=26, weight='black', transform=ax.transAxes)
    
    # 🔥 DÜZELTME: letter_spacing kaldırıldı 🔥
    plt.text(header_x, 0.90, f"RECORD: {record}", ha=header_align, va='center', 
             color=COLORS['record_text'], fontsize=12, weight='bold', transform=ax.transAxes)

    plt.text(header_x, 0.86, f"\"{one_liner}\"", ha=header_align, va='center', 
             color=COLORS['accent'], fontsize=14, style='italic', weight='bold', transform=ax.transAxes)

    # --- YETENEK BARLARI ---
    attributes = ['POWER', 'GRAPPLING', 'STAMINA', 'CHIN', 'TECHNIQUE']
    y_pos = 0.72
    bar_height = 0.02
    
    for attr in attributes:
        score = stats.get(attr.lower(), 50)
        plt.text(text_x_align, y_pos + 0.025, f"{attr}", ha='left', va='center', 
                 color=COLORS['bar_text_label'], fontsize=12, weight='bold', transform=ax.transAxes)
        plt.text(bar_start_x + bar_width + 0.02, y_pos + 0.0075, str(score), ha='left', va='center', 
                 color=COLORS['bar_text_score'], fontsize=14, weight='black', transform=ax.transAxes)

        rect_bg = patches.Rectangle((bar_start_x, y_pos), bar_width, bar_height, color=COLORS['bar_empty'], transform=ax.transAxes)
        ax.add_patch(rect_bg)
        fill_w = bar_width * (score / 100)
        rect_fill = patches.Rectangle((bar_start_x, y_pos), fill_w, bar_height, color=COLORS['bar_fill'], transform=ax.transAxes)
        ax.add_patch(rect_fill)
        
        y_pos -= 0.11

    # Logo
    plt.text(0.5, 0.03, "FIGHTIQ SCOUTING REPORT", ha='center', color='white', fontsize=10, weight='bold', alpha=0.6, transform=ax.transAxes)

    # Kaydet
    safe_name = fighter_name.replace(" ", "_")
    filename = f"{OUTPUT_DIR}/Card_{safe_name}.png"
    plt.savefig(filename, facecolor=COLORS['card_bg'], dpi=120, bbox_inches='tight')
    plt.close()

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