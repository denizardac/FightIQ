import json
import random
import os
import requests
import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv
import urllib.parse
import time # Hız kontrolü için

# Görsel Motoru
import importlib.util
try:
    spec = importlib.util.spec_from_file_location("VisualEngine", "06_visual_engine.py")
    VisualEngine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(VisualEngine)
except ImportError:
    print("❌ Error: 06_visual_engine.py not found.")
    sys.exit(1)

# Ayarlar
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_KEY)

DB_FILE = "fighters_db.json"
HISTORY_FILE = "spotlight_history.json" 
OUTPUT_FILE = "spotlight_ready.json"

def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f: 
            data = json.load(f)
            ninety_days_ago = datetime.now() - timedelta(days=90)
            return [x for x in data if datetime.strptime(x['date'], "%Y-%m-%d") > ninety_days_ago]
    except: return []

def save_history(history, name):
    history.append({"name": name, "date": datetime.now().strftime("%Y-%m-%d")})
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)

def get_random_fighter():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: db = json.load(f)
        if "data" in db: fighters = list(db["data"].keys()); urls = db["data"]
        else: fighters = list(db.keys()); urls = db 
        random.shuffle(fighters)
        return fighters, urls
    except: return [], {}

def scrape_fighter_detailed(url):
    """
    GELİŞMİŞ FİLTRELEME:
    - En az 10 Galibiyet (Tecrübe)
    - Pozitif Rekor (Galibiyet > Mağlubiyet)
    """
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        data = {"url": url}
        
        # İsim
        name_tag = soup.find('span', class_='b-content__title-highlight')
        data['name'] = name_tag.text.strip() if name_tag else "Unknown"
        
        # Record Analizi
        record_tag = soup.find('span', class_='b-content__title-record')
        data['wins'] = 0
        if record_tag:
            rec_txt = record_tag.text.split(":")[1].strip() # "29-10-0"
            data['record'] = rec_txt
            
            parts = rec_txt.split("-")
            wins = int(parts[0])
            losses = int(parts[1])
            
            # --- KRİTİK FİLTRE ---
            # 1. En az 10 galibiyet (Tecrübeli)
            # 2. Galibiyet sayısı Mağlubiyetten fazla olmalı (Pozitif Rekor)
            if wins < 10 or wins <= losses: 
                return None 
            
            data['wins'] = wins

        # İstatistikler
        for item in soup.find_all('li', class_='b-list__box-list-item_type_block'):
            text = " ".join(item.text.split())
            if "SLpM:" in text: data['slpm'] = text.split("SLpM:")[1].strip()
            if "Str. Acc.:" in text: data['str_acc'] = text.split("Str. Acc.:")[1].strip()
            if "TD Avg.:" in text: data['td_avg'] = text.split("TD Avg.:")[1].strip()
            if "Sub. Avg.:" in text: data['sub_avg'] = text.split("Sub. Avg.:")[1].strip()

        return data
    except: return None

def generate_thread_content(fighter_data):
    try:
        # Hata toleransı için model listesi
        models = ["models/gemini-2.5-pro", "models/gemini-1.5-pro-latest", "models/gemini-pro"]
        model = None
        for m_name in models:
            try: model = genai.GenerativeModel(m_name); break
            except: continue
            
        if not model: return None
        
        prompt = f"""
        ROLE: MMA Content Creator.
        TASK: Create content for UFC fighter: {fighter_data['name']}
        STATS: Record: {fighter_data.get('record')}, SLpM: {fighter_data.get('slpm')}, Sub Avg: {fighter_data.get('sub_avg')}
        
        OUTPUT JSON ONLY:
        {{
            "main_tweet": "High-energy text introducing {fighter_data['name']}. Focus on their nickname or best skill. End with a question. Max 280 chars.",
            "stat_reply": "A 'Did You Know' tweet about their stats or fighting style. Max 280 chars.",
            "card_stats": {{
                "power": (int 60-99),
                "grappling": (int 60-99),
                "stamina": (int 60-99),
                "chin": (int 60-99),
                "technique": (int 60-99),
                "one_liner": "3-5 word cool description"
            }}
        }}
        """
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"      ⚠️ AI Error: {e}")
        return None

def main():
    print("--- 🔦 STEP 9: SPOTLIGHT ENGINE (LEGEND FILTER) ---")
    
    history = load_history()
    posted_names = [h['name'] for h in history]
    fighters, urls = get_random_fighter()
    
    print(f"   🎲 Scanning for a Legend (10+ Wins & Positive Record)...")
    
    selected_data = None
    ai_content = None
    
    # 100 kişiye kadar tara ama sadece KALİTELİ olanları AI'ya sor
    scanned_count = 0
    for fname in fighters[:100]:
        if fname in posted_names: continue
        
        # Scrape işlemi hızlıdır, burada sorun yok
        data = scrape_fighter_detailed(urls[fname])
        
        if data:
            print(f"   ✨ Qualifying Candidate: {data['name']} ({data['record']})")
            
            # Rate Limit'e takılmamak için biraz bekle
            time.sleep(2) 
            
            ai_content = generate_thread_content(data)
            
            if ai_content:
                selected_data = data
                break
            else:
                print("      ⚠️ AI busy, skipping to next candidate...")
                time.sleep(5) # Hata aldıysak daha uzun bekle
        
        scanned_count += 1
    
    if not selected_data:
        print("   ❌ No suitable candidate found after scanning.")
        return

    # --- KART ÇİZİMİ ---
    print(f"   🎨 Drawing Card for: {selected_data['name']}")
    hunter = VisualEngine.ImageHunter()
    img_path = hunter.get_fighter_image(selected_data['name'])
    
    VisualEngine.create_stat_card(
        selected_data['name'],
        ai_content['card_stats'],
        ai_content['card_stats']['one_liner'],
        img_path,
        record=selected_data['record']
    )
    
    # --- YOUTUBE LINK ---
    query = f"{selected_data['name']} UFC highlights best moments"
    yt_link = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    
    # --- ÇIKTI ---
    output = {
        "fighter": selected_data['name'],
        "visual_path": f"visuals/Card_{selected_data['name'].replace(' ','_')}.png",
        "thread": [
            ai_content['main_tweet'], 
            f"📊 STAT FACT: {ai_content['stat_reply']}",
            f"📺 WATCH HIGHLIGHTS:\nCheck out {selected_data['name']} in action here: 👇\n{yt_link}"
        ]
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
        
    save_history(history, selected_data['name'])
    print(f"   ✅ Spotlight Thread Ready!")

if __name__ == "__main__":
    main()