import requests
from bs4 import BeautifulSoup
import json
import string
import time
import sys
from datetime import datetime

# ==========================================
# 🔧 FIGHTIQ: DB INDEXER (ROBUST VERSION)
# ==========================================

# Windows konsol düzeltmesi (Linux'ta zararı yok)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass 

def create_fighter_database():
    print("--- 📚 UFC FIGHTER DATABASE CREATOR ---")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    base_url = "http://ufcstats.com/statistics/fighters?char={}&page=all"
    alphabet = string.ascii_lowercase 
    fighter_db = {
        "meta": {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "ufcstats.com"
        },
        "data": {}
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    total_count = 0
    
    for char in alphabet:
        url = base_url.format(char)
        print(f"   📂 Indexing '{char.upper()}'...", end="")
        
        # --- RETRY MECHANISM (Hata Toleransı) ---
        success = False
        for attempt in range(3): # 3 kere dene
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    success = True
                    break
            except Exception as e:
                time.sleep(2) # Hata varsa 2 sn bekle ve tekrar dene
        
        if not success:
            print(" ❌ FAILED (Network Error)")
            continue
            
        # --- PARSING ---
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr', class_='b-statistics__table-row')
            
            count = 0
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 2: continue
                
                link_tag = cols[0].find('a')
                if not link_tag: continue
                
                first_name = link_tag.text.strip()
                last_name = cols[1].text.strip()
                full_name = f"{first_name} {last_name}".lower() # Küçük harfle kaydet
                
                link = link_tag['href']
                
                # Veritabanına ekle
                fighter_db["data"][full_name] = link
                count += 1
                total_count += 1
            
            print(f" ✅ Found {count}.")
            time.sleep(0.5) 
            
        except Exception as e:
            print(f" ❌ Parse Error: {e}")

    # JSON dosyasına kaydet
    with open("fighters_db.json", "w", encoding="utf-8") as f:
        json.dump(fighter_db, f, indent=4)
        
    print(f"\n🎉 Database Complete! Total Fighters: {total_count}")
    print("Saved to 'fighters_db.json'")

if __name__ == "__main__":
    create_fighter_database()