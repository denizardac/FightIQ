import requests
import xml.etree.ElementTree as ET
import json
import collections
import re
from io import BytesIO

# ==========================================
# 📈 FIGHTIQ: TREND HUNTER -> 11_trend_hunter.py
# ==========================================
RSS_URL = "https://www.sherdog.com/rss/news.xml"
DB_FILE = "fighters_db.json"

def load_fighter_names():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # data structure might be {"data": {"Name": "url", ...}} or just {"Name": "url"}
            if "data" in data: return list(data["data"].keys())
            return list(data.keys())
    except: return []

def get_trending_fighters():
    print("   📈 Trend Hunter: Scanning Sherdog RSS...")
    
    # 1. Fetch RSS
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(RSS_URL, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"      ❌ RSS Error: {resp.status_code}")
            return []
        
        # 2. Parse Titles
        tree = ET.parse(BytesIO(resp.content))
        root = tree.getroot()
        titles = []
        for item in root.findall(".//item"):
            title = item.find("title")
            if title is not None:
                titles.append(title.text)
        
        print(f"      📰 Analyzed {len(titles)} headlines.")

        # 3. Match with DB
        all_fighters = load_fighter_names()
        # Optimize: create a set for fast lookup? 
        # But headlines contain "Alex Pereira" inside "Alex Pereira wins..."
        # We need to iterate over known fighters and check if they appear in titles.
        # To be fast, limit to fighters with significant checks or reverse logic?
        # Reverse logic: Tokenize title? No, names are 2 words.
        # Naive approach: Loop through TOP fighters? No, we want trending.
        # Better approach: Loop through titles, and for each title, search for known names.
        # But sweeping 3000 names vs 20 titles is slow (3000 * 20 = 60,000 checks - fast enough for Python).
        
        counts = collections.Counter()
        
        # Pre-filter: only check fighters who have full names (2+ words) to avoid "Law" or "Just" matches
        valid_names = [n for n in all_fighters if " " in n]
        
        for title in titles:
            t_clean = title.lower() # remove punctuation?
            # Basic check
            for name in valid_names:
                if name.lower() in t_clean:
                    counts[name] += 1
        
        # Get Top 5
        trending = [name for name, count in counts.most_common(10)]
        print(f"      🔥 Trending: {trending[:3]}")
        
        if not trending:
            # Fallback randoms if news is super generic
            return []
            
        return trending

    except Exception as e:
        print(f"      ❌ Trend Error: {e}")
        return []

if __name__ == "__main__":
    t = get_trending_fighters()
    print("Result:", t)
