import json
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import difflib
import urllib.parse
import sys
import os
import re

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path
from core.pipeline_meta import stamp_stage
from core.ufcstats_http import fetch as ufcstats_fetch
import core.config as config # P2: Explicit config import

# ==========================================
# ⚙️ AYARLAR
# ==========================================
DB_FILE = get_data_path("fighters_db.json")
INPUT_FILE = get_data_path("1_card.json")
OUTPUT_FILE = get_data_path("2_data.json")

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


try:
    from bs4 import XMLParsedAsHTMLWarning
    import warnings
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:
    pass


def _parse_feed(content):
    """Parse an RSS/Atom feed, tolerating a missing lxml install.

    BeautifulSoup's 'xml' feature REQUIRES lxml; when it's absent every news
    fetch used to raise FeatureNotFound and the AI prompt got zero headlines.
    Fall back to the always-available stdlib html.parser (good enough for
    reading <item><title> text).
    """
    for parser in ("xml", "lxml-xml", "html.parser"):
        try:
            return BeautifulSoup(content, parser)
        except Exception:
            continue
    return BeautifulSoup(content, "html.parser")


class SmartScraper:
    def __init__(self):
        self.ua = UserAgent()
        # Veritabanını yükle
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                self.db_content = json.load(f)
                if "data" in self.db_content:
                    self.db = self.db_content["data"]
                else:
                    self.db = self.db_content 
            print(f"📚 Database Loaded: {len(self.db)} fighters ready.")
            
            if len(self.db) < 100:
                print("⚠️ WARNING: Database seems empty! Run '00_indexer.py' first.")
                
        except FileNotFoundError:
            print("❌ HATA: 'fighters_db.json' bulunamadı! Önce 00_indexer.py çalıştır.")
            self.db = {}

    def _get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://google.com'
        }

    # --- 1. İSİM BULUCU ---
    def find_fighter_url(self, name):
        clean_name = name.lower().strip()
        if clean_name in self.db:
            return self.db[clean_name]
        
        # Use higher cutoff for better accuracy (0.8 instead of 0.6)
        matches = difflib.get_close_matches(clean_name, self.db.keys(), n=1, cutoff=config.FUZZY_MATCH_CUTOFF)
        if matches:
            found_name = matches[0]
            print(f"   💡 Fuzzy Match: '{name}' -> '{found_name}'")
            return self.db[found_name]
        return None

    # --- 2. İSTATİSTİK & GÖRSEL ÇEKİCİ ---
    def scrape_stats(self, url):
        if not url: return {}

        resp = None
        for attempt in range(3):
            try:
                resp = ufcstats_fetch(url, headers=self._get_headers())
                if resp.status_code == 200:
                    break
                resp = None
            except Exception as e:
                print(f"      ⚠️ Stats fetch attempt {attempt+1}: {type(e).__name__}: {str(e)[:60]}")
                resp = None
                time.sleep(1)
        if not resp:
            return {}

        try:
            soup = BeautifulSoup(resp.text, 'html.parser')
            metrics = {}
            
            # A. TEMEL İSTATİSTİKLER
            for item in soup.find_all('li', class_='b-list__box-list-item_type_block'):
                text = " ".join(item.text.split())
                if "SLpM:" in text: metrics['SLpM'] = text.split("SLpM:")[1].strip()
                if "Str. Acc.:" in text: metrics['Str_Acc'] = text.split("Str. Acc.:")[1].strip()
                if "SApM:" in text: metrics['SApM'] = text.split("SApM:")[1].strip()
                if "Str. Def:" in text: metrics['Str_Def'] = text.split("Str. Def:")[1].strip()
                if "TD Avg.:" in text: metrics['TD_Avg'] = text.split("TD Avg.:")[1].strip()
                if "TD Acc.:" in text: metrics['TD_Acc'] = text.split("TD Acc.:")[1].strip()
                if "TD Def.:" in text: metrics['TD_Def'] = text.split("TD Def.:")[1].strip()
                if "Sub. Avg.:" in text: metrics['Sub_Avg'] = text.split("Sub. Avg.:")[1].strip()

            # Tale of the tape (same page — used when deep_dive row layout differs)
            for item in soup.find_all("li", class_=re.compile(r"b-list__box-list-item")):
                text = " ".join(item.get_text().split())
                if "Height:" in text:
                    metrics["Height"] = text.split("Height:", 1)[1].strip()
                elif "Weight:" in text:
                    metrics["Weight"] = text.split("Weight:", 1)[1].strip()
                elif "Reach:" in text:
                    metrics["reach"] = text.replace("Reach:", "").strip()
                elif "STANCE:" in text.upper() or "stance:" in text.lower():
                    metrics["stance"] = text.split(":", 1)[-1].strip()

            # B. LAKAP (Nickname)
            nickname = ""
            nick_tag = soup.find('p', class_='b-content__Nickname')
            if nick_tag:
                nickname = nick_tag.get_text(strip=True)
            metrics['Nickname'] = nickname

            # C. FOTOĞRAF (Image URL)
            # UFCStats'ta resimler genelde 'b-fight-details__person-img' class'lı img tagindedir
            img_tag = soup.find('img', class_='b-fight-details__person-img') # Bu class değişebilir, kontrol edelim
            # Alternatif yapı: Carousel içindeki resim
            if not img_tag:
                img_tag = soup.select_one(".b-content__image img")
            
            if img_tag and 'src' in img_tag.attrs:
                # Varsayılan "siluet" resmi değilse al
                if "silhouette" not in img_tag['src']:
                    metrics['Image_URL'] = img_tag['src']
                else:
                    metrics['Image_URL'] = None # Resim yok
            else:
                metrics['Image_URL'] = None

            return metrics
            
        except Exception as e:
            print(f"      ⚠️ Stats Error: {e}")
            return {}

    # --- 3. HABER ÇEKİCİ (MULTI-SOURCE) ---
    def get_news(self, name):
        """Çoklu kaynaklardan haber topla"""
        all_news = []
        
        # Source 1: Google News RSS
        try:
            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(name)}+UFC&hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss_url, headers=self._get_headers(), timeout=10)
            soup = _parse_feed(resp.content)
            for item in soup.find_all('item', limit=2):
                all_news.append({
                    "title": item.title.text,
                    "date": item.pubDate.text if item.pubDate else "N/A",
                    "link": item.link.text if item.link else "",
                    "source": "Google News"
                })
        except Exception as e:
            print(f"      ⚠️ Google News RSS failed: {type(e).__name__}: {str(e)[:60]}")
        
        # Source 2: MMA Fighting RSS (dedicated MMA site)
        try:
            mma_rss = f"https://www.mmafighting.com/rss/index.xml"
            resp = requests.get(mma_rss, headers=self._get_headers(), timeout=8)
            soup = _parse_feed(resp.content)
            for item in soup.find_all('item'):
                title = item.title.text if item.title else ""
                # Only include if fighter name mentioned
                if name.lower() in title.lower():
                    all_news.append({
                        "title": title,
                        "date": item.pubDate.text if item.pubDate else "N/A",
                        "link": item.link.text if item.link else "",
                        "source": "MMA Fighting"
                    })
                    if len(all_news) >= 4: break
        except Exception as e:
            print(f"      ⚠️ MMA Fighting RSS failed: {type(e).__name__}: {str(e)[:60]}")
        
        # Source 3: ESPN MMA RSS
        try:
            espn_rss = "https://www.espn.com/espn/rss/mma/news"
            resp = requests.get(espn_rss, headers=self._get_headers(), timeout=8)
            soup = _parse_feed(resp.content)
            for item in soup.find_all('item'):
                title = item.title.text if item.title else ""
                if name.lower() in title.lower():
                    all_news.append({
                        "title": title,
                        "date": item.pubDate.text if item.pubDate else "N/A",
                        "link": item.link.text if item.link else "",
                        "source": "ESPN MMA"
                    })
                    if len(all_news) >= 5: break
        except Exception as e:
            print(f"      ⚠️ ESPN RSS failed: {type(e).__name__}: {str(e)[:60]}")
        
        # Return top 3 most recent
        return all_news[:3] if all_news else []

def main():
    print("--- STEP 2: STAT SCOUT (DATA MINING v2) ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            card_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ '{INPUT_FILE}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ '{INPUT_FILE}' contains invalid JSON: {e}")
        sys.exit(1)

    bot = SmartScraper()

    # DB kontrolü
    if len(bot.db) < 100:
        print("🛑 STOPPING: Database is nearly empty. Please run '00_indexer.py' fully.")
        sys.exit(1)

    enriched_fights = []
    fights = card_data.get('fights', [])
    print(f"🏆 Event: {card_data.get('event', 'Unknown')}")
    
    for i, fight in enumerate(fights):
        f1_name = fight['f1']
        f2_name = fight['f2']
        
        print(f"\n🥊 [{i+1}/{len(fights)}] Scouting: {f1_name} vs {f2_name}")
        
        link1 = bot.find_fighter_url(f1_name)
        link2 = bot.find_fighter_url(f2_name)
        
        if not link1: print(f"      ❌ URL Not Found for: {f1_name}")
        if not link2: print(f"      ❌ URL Not Found for: {f2_name}")
        
        stats1 = bot.scrape_stats(link1) if link1 else {}
        stats2 = bot.scrape_stats(link2) if link2 else {}
        
        if stats1: 
            img_status = "📸 Found" if stats1.get('Image_URL') else "No Image"
            print(f"      ✅ Stats F1: OK ({img_status})")
        
        if stats2: 
            img_status = "📸 Found" if stats2.get('Image_URL') else "No Image"
            print(f"      ✅ Stats F2: OK ({img_status})")
        
        news1 = bot.get_news(f1_name)
        news2 = bot.get_news(f2_name)
        
        enriched_fights.append({
            "fighters": [f1_name, f2_name],
            "urls": [link1, link2],
            "stats": [stats1, stats2],
            "news": [news1, news2]
        })
        
        time.sleep(1)

    if fights and not enriched_fights:
        print("❌ No fights could be enriched — failing so the pipeline stops.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched_fights, f, indent=4)
    stamp_stage("2_data", card_data.get("event", ""))

    print(f"\n✅ SUCCESS: Data mined for {len(enriched_fights)} fights.")
    print(f"📁 Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()