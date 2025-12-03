import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime

# --- AYARLAR ---
INPUT_FILE = "2_data_with_odds.json"
OUTPUT_FILE = "2_data_final.json"

class DeepStatsEngine:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def time_to_seconds(self, time_str):
        """04:20 formatını saniyeye çevirir"""
        try:
            if not ":" in time_str: return 0
            m, s = map(int, time_str.split(':'))
            return m * 60 + s
        except: return 0

    def calculate_age(self, dob_str):
        """ 'Oct 23, 1990' formatından yaş hesaplar """
        try:
            dob_str = " ".join(dob_str.split()) # Fazla boşlukları sil
            if not dob_str or dob_str == "--": return "N/A"
            dob = datetime.strptime(dob_str, "%b %d, %Y")
            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except: return "N/A"

    def analyze_fighter_profile(self, url):
        """Bir dövüşçünün tüm kariyer geçmişini ve fiziksel özelliklerini analiz eder"""
        if not url: return None
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            stats = {
                "name": "", # İsim kontrolü için
                "reach": "N/A",
                "stance": "N/A",
                "age": "N/A",
                "total_fights": 0,
                "wins": 0,
                "losses": 0,
                "win_by_ko": 0,
                "win_by_sub": 0,
                "win_by_dec": 0,
                "first_round_finishes": 0,
                "avg_fight_time_sec": 0,
                "last_5_results": [] 
            }
            
            # --- 1. Fiziksel Özellikler (Header) ---
            # İsim
            name_tag = soup.find('span', class_='b-content__title-highlight')
            if name_tag: stats['name'] = name_tag.get_text(strip=True)

            # Detaylar kutusu (Height, Weight, Reach, STANCE, DOB)
            box_items = soup.find_all('li', class_='b-list__box-list-item')
            for item in box_items:
                text = " ".join(item.get_text().split())
                if "Reach:" in text:
                    stats['reach'] = text.replace("Reach:", "").strip()
                elif "STANCE:" in text:
                    stats['stance'] = text.replace("STANCE:", "").strip()
                elif "DOB:" in text:
                    dob_raw = text.replace("DOB:", "").strip()
                    stats['age'] = self.calculate_age(dob_raw)

            # --- 2. Geçmiş Maçlar Tablosunu Bul ---
            rows = soup.find_all('tr', class_='b-fight-details__table-row')
            
            total_seconds_fought = 0
            fight_count_for_time = 0
            
            # İlk satır başlıktır, onu atla
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) < 10: continue
                
                try:
                    result_text = cols[0].get_text(strip=True) # win/loss
                    method = cols[7].get_text(strip=True) # KO/TKO
                    round_num = cols[8].get_text(strip=True)
                    time_str = cols[9].get_text(strip=True)
                    
                    stats["total_fights"] += 1
                    
                    if len(stats["last_5_results"]) < 5:
                        stats["last_5_results"].append(result_text)

                    if result_text == 'win':
                        stats["wins"] += 1
                        if "KO" in method or "TKO" in method:
                            stats["win_by_ko"] += 1
                        elif "Sub" in method:
                            stats["win_by_sub"] += 1
                        elif "Dec" in method:
                            stats["win_by_dec"] += 1
                        
                        if round_num == "1" and ("KO" in method or "Sub" in method):
                            stats["first_round_finishes"] += 1

                    elif result_text == 'loss':
                        stats["losses"] += 1

                    if round_num.isdigit():
                        r = int(round_num)
                        t_sec = self.time_to_seconds(time_str)
                        match_seconds = ((r - 1) * 300) + t_sec
                        total_seconds_fought += match_seconds
                        fight_count_for_time += 1
                        
                except Exception: continue

            # Ortalamalar
            if stats["wins"] > 0:
                stats["ko_rate"] = round((stats["win_by_ko"] / stats["wins"]) * 100, 1)
                stats["sub_rate"] = round((stats["win_by_sub"] / stats["wins"]) * 100, 1)
            else:
                stats["ko_rate"] = 0
                stats["sub_rate"] = 0
                
            if fight_count_for_time > 0:
                avg_sec = total_seconds_fought / fight_count_for_time
                m = int(avg_sec // 60)
                s = int(avg_sec % 60)
                stats["avg_fight_time"] = f"{m}:{s:02d}"
            else:
                stats["avg_fight_time"] = "0:00"

            return stats

        except Exception as e:
            print(f"      ⚠️ Profile parsing error: {e}")
            return None

def main():
    print("--- 🧬 STEP 2.5: DEEP STATS ENGINE (WITH STANCE/REACH) ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except: 
        print(f"❌ '{INPUT_FILE}' not found.")
        return

    engine = DeepStatsEngine()
    
    for fight in data:
        f1_name, f2_name = fight['fighters']
        print(f"\n📊 Analyzing: {f1_name} vs {f2_name}")
        
        urls = fight.get('urls', [])
        if len(urls) < 2:
            print("   ❌ Missing URLs.")
            continue
            
        deep1 = engine.analyze_fighter_profile(urls[0])
        deep2 = engine.analyze_fighter_profile(urls[1])
        
        if deep1 and deep2:
            fight['deep_stats'] = [deep1, deep2]
            
            # --- DEBUG INFO ---
            print(f"      ✅ {f1_name}: {deep1['age']} yrs | {deep1['stance']} | Reach: {deep1['reach']}")
            print(f"      ✅ {f2_name}: {deep2['age']} yrs | {deep2['stance']} | Reach: {deep2['reach']}")
            print(f"      🔥 Style: {deep1['ko_rate']}% KO vs {deep2['ko_rate']}% KO")
        else:
            print("      ⚠️ Failed to extract deep stats.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n📁 Final Data Saved to '{OUTPUT_FILE}'")
    print("🚀 Ready for Step 3 (AI Analysis)")

if __name__ == "__main__":
    main()