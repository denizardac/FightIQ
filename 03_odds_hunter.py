import requests
from bs4 import BeautifulSoup
import json
import re
import difflib
import time

# --- AYARLAR ---
INPUT_FILE = "2_data.json"
OUTPUT_FILE = "2_data_with_odds.json"
UFC_LEAGUE_ID = "41875249"

# Bu link bizi her zaman güncel adrese atar
REDIRECT_URL = "https://cutt.ly/zrIT6E9d" 

class BetistEngine:
    def __init__(self):
        self.fighter_to_id = {} 
        self.base_domain = None
        self.base_url = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def resolve_current_domain(self):
        """Redirect linkini takip edip güncel Betist adresini bulur."""
        print("   🕵️‍♂️ Resolving current Betist domain...")
        try:
            # allow_redirects=True ile yönlendirmeyi takip et
            # verify=False SSL hatalarını önler (bazen redirectlerde sertifika sorunu olur)
            session = requests.Session()
            resp = session.get(REDIRECT_URL, headers={'User-Agent': self.headers['User-Agent']}, timeout=15, allow_redirects=True, verify=False)
            
            final_url = resp.url
            print(f"      ↳ Redirected to: {final_url}")
            
            # Domaini ayıkla (https://betist1573.com/...)
            # Regex ile "betist" ve sonrasındaki sayıyı bulalım
            match = re.search(r'(betist\d+)', final_url)
            
            if match:
                site_name = match.group(1) # örn: betist1573
                # API subdomaini genellikle "bet." ile başlar
                self.base_domain = f"bet.{site_name}.com"
                self.base_url = f"https://{self.base_domain}/getdata.php"
                
                # Referer header'ını güncelle
                self.headers['Referer'] = f"https://{self.base_domain}/"
                print(f"   ✅ Target API set to: {self.base_url}")
                return True
            else:
                print("   ❌ Could not parse domain from redirect URL.")
                # Fallback: Manuel bildiğimiz son adresi deneyelim
                print("   ⚠️ Falling back to hardcoded domain...")
                self.base_domain = "bet.betist1573.com"
                self.base_url = f"https://{self.base_domain}/getdata.php"
                return True
                
        except Exception as e:
            print(f"   ❌ Domain resolution failed: {e}")
            return False

    def clean_name(self, name):
        return " ".join(name.lower().split())

    def fetch_event_list(self):
        if not self.base_url: return
        
        print(f"   📡 Fetching UFC Event List from {self.base_domain}...")
        params = {
            'sec': 'ASIAN_LAYOUT',
            'subsec': 'REQUEST_GET_SCHEME_EVENTS',
            'league_id[]': UFC_LEAGUE_ID,
            'layout_schema_code': 'single_line_betist_1x2',
            'selected_date_period': 'null'
        }
        try:
            resp = requests.get(self.base_url, params=params, headers=self.headers, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            rows = soup.find_all('tbody', class_='cont_odds_row')
            
            count = 0
            for row in rows:
                try:
                    name_span = row.find('span', class_='not_favorite_part')
                    if not name_span: continue
                    full_name_text = name_span.get_text(strip=True)
                    
                    count_cell = row.find('td', class_='m-bet-grid__cell_count')
                    if not count_cell: continue
                    
                    onclick_text = count_cell.get('onclick', '')
                    id_match = re.search(r'(\d+)', onclick_text)
                    
                    if id_match:
                        event_id = id_match.group(1)
                        fighters = full_name_text.split('-')
                        for f in fighters:
                            clean_f = self.clean_name(f)
                            if len(clean_f) > 3: 
                                self.fighter_to_id[clean_f] = event_id
                        count += 1
                except: continue
            print(f"   ✅ Successfully indexed {count} fights.")
        except Exception as e:
            print(f"   ❌ List fetch failed: {e}")

    def get_event_id_smart(self, f1, f2):
        f1_clean = self.clean_name(f1)
        for db_name, ev_id in self.fighter_to_id.items():
            f1_parts = set(f1_clean.split())
            db_parts = set(db_name.split())
            intersection = f1_parts.intersection(db_parts)
            if len(intersection) >= len(f1_parts) - 1: 
                return ev_id
        
        all_db_names = list(self.fighter_to_id.keys())
        match = difflib.get_close_matches(f1_clean, all_db_names, n=1, cutoff=0.6)
        if match: return self.fighter_to_id[match[0]]
        
        f2_clean = self.clean_name(f2)
        match2 = difflib.get_close_matches(f2_clean, all_db_names, n=1, cutoff=0.6)
        if match2: return self.fighter_to_id[match2[0]]

        return None

    def parse_complex_market(self, text, market_name, f1_name, f2_name):
        if market_name not in text: return None
        start_idx = text.find(market_name) + len(market_name)
        snippet = text[start_idx:start_idx+1500]
        extracted_odds = {}
        
        patterns = [
            (r'W1\s+(.*?)\s+(\d+\.\d{2})', f"{f1_name}"), 
            (r'W2\s+(.*?)\s+(\d+\.\d{2})', f"{f2_name}"),
            (f"({f1_name}.*?)\\s+(\\d+\\.\\d{{2}})", "Winner"),
            (f"({f2_name}.*?)\\s+(\\d+\\.\\d{{2}})", "Winner"),
            (r'(Yes)\s+(\d+\.\d{2})', "Yes"),
            (r'(No)\s+(\d+\.\d{2})', "No"),
            (r'(Fight to be Won.*?)\s+(\d+\.\d{2})', "TimeProp"),
            (r'(Winner in Round \d+)\s+(\d+\.\d{2})', "RoundProp"),
            (r'(Over)\s+(\d+\.\d{2})', "Over"),
            (r'(Under)\s+(\d+\.\d{2})', "Under")
        ]
        
        for pattern, type_label in patterns:
            matches = re.findall(pattern, snippet, re.IGNORECASE)
            for match in matches:
                label = match[0].strip()
                odd = float(match[1])
                if len(label) < 2 or label.replace('.','').isdigit(): continue
                
                if type_label not in ["Yes", "No", "Over", "Under", "Winner", "TimeProp", "RoundProp"]:
                    full_label = f"{type_label} - {label}"
                else:
                    full_label = label
                extracted_odds[full_label] = odd
                
        return extracted_odds if extracted_odds else None

    def fetch_market_details(self, event_id, f1, f2):
        if not self.base_url: return None
        
        url = f"{self.base_url}?sec=ASIAN_LAYOUT&subsec=REQUEST_GET_ADDITIONAL_MARKETS&event_id={event_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10, verify=False)
            soup = BeautifulSoup(resp.content, 'html.parser')
            text = soup.get_text(" ", strip=True)
            
            markets = {}
            m_winner = re.search(r'1\s+(\d+\.\d+)\s*2\s+(\d+\.\d+)', text)
            if m_winner:
                markets['Moneyline'] = {f1: float(m_winner.group(1)), f2: float(m_winner.group(2))}

            target_markets = [
                "Fight To Start Round 3", "Fight to Go the Distance", "Total Rounds",
                "Winning Method", "Alternative Winning Method", "Winning Round",
                "Winning Group of Rounds", "Gone in 60 Seconds", "Winning Round and Minute"
            ]
            
            for target in target_markets:
                odds = self.parse_complex_market(text, target, f1, f2)
                if odds:
                    if target == "Total Rounds":
                        idx = text.find("Total Rounds")
                        line_match = re.search(r'\(([\d\.]+)\)', text[idx:idx+50])
                        key = f"Total Rounds ({line_match.group(1)})" if line_match else "Total Rounds"
                        markets[key] = odds
                    else:
                        markets[target] = odds
            return markets
        except Exception as e:
            return {"error": str(e)}

def main():
    import urllib3
    urllib3.disable_warnings() # SSL uyarılarını sustur
    
    print("--- 💰 BETIST AUTO-PILOT ENGINE ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except: 
        print(f"❌ '{INPUT_FILE}' not found.")
        return

    engine = BetistEngine()
    
    # 1. Domaini Bul
    if not engine.resolve_current_domain():
        print("❌ Critical Error: Could not resolve domain.")
        return

    # 2. Listeyi Çek
    engine.fetch_event_list()
    
    found_count = 0
    for fight in data:
        f1, f2 = fight['fighters'][0], fight['fighters'][1]
        print(f"\n🔍 {f1} vs {f2}")
        
        ev_id = engine.get_event_id_smart(f1, f2)
        if ev_id:
            print(f"   ✅ ID: {ev_id}")
            odds = engine.fetch_market_details(ev_id, f1, f2)
            if odds:
                fight['betist_odds'] = odds
                found_count += 1
                print(f"      📊 Markets Found: {len(odds)} categories")
            else:
                print("      ⚠️ Markets empty.")
        else:
            print("      ❌ ID Not Found")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n📁 Saved to '{OUTPUT_FILE}'. Matches: {found_count}/{len(data)}")

if __name__ == "__main__":
    main()