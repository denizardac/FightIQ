import requests
import xml.etree.ElementTree as ET
import json
import collections
import re
from io import BytesIO
import sys
import os

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

# ==========================================
# 📈 FIGHTIQ: TREND HUNTER -> 11_trend_hunter.py
# ==========================================
RSS_URL = "https://www.sherdog.com/rss/news.xml"
DB_FILE = get_data_path("fighters_db.json")

def load_fighter_names():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # data structure might be {"data": {"Name": "url", ...}} or just {"Name": "url"}
            if "data" in data: return list(data["data"].keys())
            return list(data.keys())
    except: return []

def get_trending_fighters():
    print("   📈 Trend Hunter: Scanning MMA News Sources...")
    
    # HYDRA APPROACH: Verified working sources + Google News fallback
    RSS_SOURCES = [
        ("Low Kick MMA", "https://www.lowkickmma.com/feed/"),
        ("MMA Junkie", "https://mmajunkie.usatoday.com/feed"),
        ("MMA Fighting", "https://www.mmafighting.com/rss/current"),
        ("Bloody Elbow", "https://www.bloodyelbow.com/rss/index.xml"),
        ("MMA Mania", "https://www.mmamania.com/rss/index.xml"),
        ("Sherdog", "https://www.sherdog.com/rss/news.xml"),
        ("ESPN MMA", "https://www.espn.com/espn/rss/mma/news"),
        ("Google News UFC", "https://news.google.com/rss/search?q=UFC&hl=en-US&gl=US&ceid=US:en"),
    ]
    
    all_titles = []
    successful_sources = 0
    
    # Try each source
    for source_name, rss_url in RSS_SOURCES:
        try:
            # Rotate User-Agents to avoid 403 blocking
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
            ]
            
            import random
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': rss_url.split('/')[0] + '//' + rss_url.split('/')[2] + '/',
                'Cache-Control': 'no-cache'
            }
            
            resp = requests.get(rss_url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                print(f"      ⚠️ {source_name} returned {resp.status_code}, trying next...")
                continue
            
            # Parse titles (handle both standard RSS and Atom feeds)
            try:
                tree = ET.parse(BytesIO(resp.content))
                root = tree.getroot()
                titles = []
                
                # Try standard RSS format
                for item in root.findall(".//item"):
                    title = item.find("title")
                    if title is not None:
                        titles.append(title.text)
                
                # Try Atom format (e.g., Google News)
                if not titles:
                    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                        title = entry.find("{http://www.w3.org/2005/Atom}title")
                        if title is not None:
                            titles.append(title.text)
                
                if titles:
                    all_titles.extend(titles)
                    successful_sources += 1
                    print(f"      ✅ {source_name}: {len(titles)} headlines")
                else:
                    print(f"      ⚠️ {source_name}: No titles found")
            except ET.ParseError as e:
                print(f"      ❌ {source_name} XML parse error")
                continue
            
        except Exception as e:
            print(f"      ❌ {source_name} error: {str(e)[:50]}")
            continue
    
    if not all_titles:
        print(f"      ❌ All {len(RSS_SOURCES)} RSS sources failed")
        return []
    
    print(f"      📰 Success: {successful_sources}/{len(RSS_SOURCES)} sources, {len(all_titles)} total headlines")

    # 3. Match with DB
    all_fighters = load_fighter_names()
    counts = collections.Counter()

    # Two-stage match:
    #   • Multi-word names → substring match (cheap and accurate)
    #   • Single-word names → word-boundary regex to avoid false positives
    multi_word = [n for n in all_fighters if " " in n]
    single_word = [n for n in all_fighters if " " not in n and len(n) >= 4]
    single_word_re = {n: re.compile(rf"\b{re.escape(n.lower())}\b") for n in single_word}

    for title in all_titles:
        if not title:
            continue
        t_clean = title.lower()
        for name in multi_word:
            if name.lower() in t_clean:
                counts[name] += 1
        for name, pat in single_word_re.items():
            if pat.search(t_clean):
                counts[name] += 1
    
    # Get Top 10
    trending = [name for name, count in counts.most_common(10)]
    print(f"      🔥 Trending: {trending[:3]}")
    
    if not trending:
        return []
        
    return trending

if __name__ == "__main__":
    t = get_trending_fighters()
    print("Result:", t)
