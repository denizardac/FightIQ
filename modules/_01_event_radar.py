import json
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
import sys
import re
import os

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

# ==========================================
# ⚙️ AYARLAR
# ==========================================
OUTPUT_FILE = get_data_path("1_card.json")
# Maç haftası limiti (6 gün önceden başlar, Cumartesi 0. gün olur)
FIGHT_WEEK_LIMIT = 6 

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

def parse_ufc_date(raw_text):
    try:
        # Metin temizliği (PimblettJanuary -> Pimblett January)
        clean_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_text)
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', clean_text, re.IGNORECASE)
        if match:
            return datetime.strptime(match.group(0), "%B %d, %Y")
        return None
    except: return None

def fetch_event(ua):
    url = "http://ufcstats.com/statistics/events/upcoming"
    print(f"   🌐 Checking: {url}")
    try:
        resp = requests.get(url, headers={'User-Agent': ua.random}, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # İlk etkinliği bul
        rows = soup.find_all('tr', class_='b-statistics__table-row')
        target_row = None
        for row in rows:
            if row.find('a'):
                target_row = row
                break
        
        if not target_row: return None
        
        link = target_row.find('a')
        date_text = "Unknown"
        for col in target_row.find_all('td'):
            txt = col.get_text(strip=True)
            if any(m in txt for m in ['January', 'February', 'March', 'April', 'May']):
                date_text = txt
                break
        
        return link.text.strip(), link['href'], date_text
    except: return None

def main():
    print("--- 📡 STEP 1: EVENT RADAR (CALENDAR SYNC) ---")
    ua = UserAgent()
    
    event_data = fetch_event(ua)
    if not event_data:
        print("   ❌ No events found.")
        # Fallback mekanizması buraya eklenebilir ama şimdilik IDLE döner
        return

    name, url, date_txt = event_data
    print(f"   🎯 Event: {name}")
    
    # Tarih Hesaplama
    event_date = parse_ufc_date(date_txt)
    status = "IDLE"
    days_diff = 999
    final_date = date_txt
    
    if event_date:
        # Bugün ile Maç Günü arasındaki fark
        days_diff = (event_date - datetime.now()).days + 1
        final_date = event_date.strftime("%Y-%m-%d")
        print(f"   ⏳ Days Until Fight: {days_diff}")
        
        # --- KRİTİK MOD SEÇİMİ ---
        # 0 = Bugün Maç Var (Cumartesi)
        # 1-6 = Maç Haftası (Pazar'dan Cuma'ya kadar olan süreç)
        if 0 <= days_diff <= FIGHT_WEEK_LIMIT:
            print("   🔥 STATUS: FIGHT WEEK! (LIVE)")
            status = "LIVE"
        else:
            print("   ☕ STATUS: OFF-SEASON / BUILD-UP (IDLE)")
            status = "IDLE"
    
    # Kartı Çek
    fights = []
    try:
        c_resp = requests.get(url, headers={'User-Agent': ua.random})
        c_soup = BeautifulSoup(c_resp.text, 'html.parser')
        for r in c_soup.find_all('tr', class_='b-fight-details__table-row'):
            cols = r.find_all('td')
            if len(cols) >= 2:
                ns = cols[1].find_all('a')
                if len(ns) >= 2: fights.append({"f1": ns[0].text.strip(), "f2": ns[1].text.strip()})
    except: pass

    output = {
        "event": name, "date": final_date, "status": status, 
        "days_until": days_diff, "url": url, "fights": fights
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f: json.dump(output, f, indent=4)
    print(f"   📁 Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()