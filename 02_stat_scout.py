import json
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import difflib
import urllib.parse

# ==========================================
# ⚙️ AYARLAR
# ==========================================
DB_FILE = "fighters_db.json"
INPUT_FILE = "1_card.json"
OUTPUT_FILE = "2_data.json"

class SmartScraper:
    def __init__(self):
        self.ua = UserAgent()
        # Veritabanını yükle
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                self.db = json.load(f)
            print(f"📚 Database Loaded: {len(self.db)} fighters ready.")
        except FileNotFoundError:
            print("❌ HATA: 'fighters_db.json' bulunamadı! Önce veritabanını oluştur.")
            self.db = {}

    def _get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://google.com'
        }

    # --- 1. İSİM BULUCU (Fuzzy Logic) ---
    def find_fighter_url(self, name):
        # 1. Tam Eşleşme Dene
        clean_name = name.lower().strip()
        if clean_name in self.db:
            return self.db[clean_name]
        
        # 2. Yakın Eşleşme Dene (Örn: "Alex Volkanovski" -> "Alexander Volkanovski")
        matches = difflib.get_close_matches(clean_name, self.db.keys(), n=1, cutoff=0.6)
        if matches:
            found_name = matches[0]
            print(f"   💡 Fuzzy Match: '{name}' -> '{found_name}'")
            return self.db[found_name]
            
        return None

    # --- 2. İSTATİSTİK ÇEKİCİ (Live Scraping) ---
    def scrape_stats(self, url):
        if not url: return {}
        
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            metrics = {}
            
            # UFCStats sayfasındaki blokları gez
            for item in soup.find_all('li', class_='b-list__box-list-item_type_block'):
                text = " ".join(item.text.split())
                
                # Temel Veriler
                if "SLpM:" in text: metrics['SLpM'] = text.split("SLpM:")[1].strip()
                if "Str. Acc.:" in text: metrics['Str_Acc'] = text.split("Str. Acc.:")[1].strip()
                if "SApM:" in text: metrics['SApM'] = text.split("SApM:")[1].strip()
                if "Str. Def:" in text: metrics['Str_Def'] = text.split("Str. Def:")[1].strip()
                if "TD Avg.:" in text: metrics['TD_Avg'] = text.split("TD Avg.:")[1].strip()
                if "TD Acc.:" in text: metrics['TD_Acc'] = text.split("TD Acc.:")[1].strip()
                if "TD Def.:" in text: metrics['TD_Def'] = text.split("TD Def.:")[1].strip()
                if "Sub. Avg.:" in text: metrics['Sub_Avg'] = text.split("Sub. Avg.:")[1].strip()
            
            # Fiziksel Veriler (Height, Reach, Stance)
            # Bu veriler genellikle başka bir bloktadır, şimdilik metrikleri döndürelim
            return metrics
            
        except Exception as e:
            print(f"      ⚠️ Stats Error: {e}")
            return {}

    # --- 3. HABER ÇEKİCİ (Google RSS) ---
    def get_news(self, name):
        try:
            # Google News RSS (En kararlı yöntem)
            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(name)}+UFC&hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss_url, headers=self._get_headers(), timeout=10)
            soup = BeautifulSoup(resp.content, 'xml')
            
            news_items = []
            for item in soup.find_all('item', limit=3): # Son 3 haber
                news_items.append({
                    "title": item.title.text,
                    "date": item.pubDate.text if item.pubDate else "N/A"
                })
            return news_items
        except:
            return []

def main():
    print("--- STEP 2: SMART DATA GATHERING ---")
    
    # 1. Kartı Yükle
    try:
        with open(INPUT_FILE, "r") as f:
            card_data = json.load(f)
    except FileNotFoundError:
        print("❌ HATA: '1_card.json' bulunamadı! Önce step1 çalıştır.")
        return

    bot = SmartScraper()
    enriched_fights = []
    
    print(f"🏆 Event: {card_data.get('event', 'Unknown Event')}")
    
    # 2. Her Maçı İşle
    for i, fight in enumerate(card_data['fights']):
        f1_name = fight['f1']
        f2_name = fight['f2']
        
        print(f"\n🥊 Processing {i+1}/{len(card_data['fights'])}: {f1_name} vs {f2_name}")
        
        # --- A. Linkleri Bul ---
        link1 = bot.find_fighter_url(f1_name)
        link2 = bot.find_fighter_url(f2_name)
        
        if not link1: print(f"      ❌ URL Not Found for: {f1_name}")
        if not link2: print(f"      ❌ URL Not Found for: {f2_name}")
        
        # --- B. Verileri Çek (Varsa) ---
        stats1 = bot.scrape_stats(link1) if link1 else {}
        stats2 = bot.scrape_stats(link2) if link2 else {}
        
        if stats1: print("      ✅ Stats F1: OK")
        if stats2: print("      ✅ Stats F2: OK")
        
        # --- C. Haberleri Çek ---
        news1 = bot.get_news(f1_name)
        news2 = bot.get_news(f2_name)
        
        # --- D. Paketi Hazırla ---
        enriched_fights.append({
            "fighters": [f1_name, f2_name],
            "urls": [link1, link2],
            "stats": [stats1, stats2],
            "news": [news1, news2],
            # Odds şimdilik placeholder, sonraki sürümde eklenecek
            "odds_context": "Odds extraction module pending..." 
        })
        
        # Kibarlık beklemesi
        time.sleep(1)

    # 3. Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched_fights, f, indent=4)
        
    print(f"\n✅ SUCCESS: Data gathered for {len(enriched_fights)} fights.")
    print(f"📁 Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()