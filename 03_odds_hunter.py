import requests
from bs4 import BeautifulSoup
import json
import re
import difflib
import time
import sys

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = "2_data.json"
OUTPUT_FILE = "2_data_with_odds.json"
REDIRECT_URL = "https://cutt.ly/zrIT6E9d" 

# Windows konsol UTF-8 ayarı
try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

class BetistEngine:
    def __init__(self):
        self.fighter_to_id = {} 
        self.base_domain = None
        self.base_url = None
        self.active_league_id = None # Dinamik olarak bulunacak
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def resolve_current_domain(self):
        print("   🕵️‍♂️ Resolving current Betist domain...")
        try:
            session = requests.Session()
            resp = session.get(REDIRECT_URL, headers={'User-Agent': self.headers['User-Agent']}, timeout=15, allow_redirects=True, verify=False)
            
            final_url = resp.url
            print(f"      ↳ Redirected to: {final_url}")
            
            match = re.search(r'(betist\d+)', final_url)
            
            if match:
                site_name = match.group(1) 
                self.base_domain = f"bet.{site_name}.com"
                self.base_url = f"https://{self.base_domain}/getdata.php"
                self.headers['Referer'] = f"https://{self.base_domain}/"
                print(f"   ✅ Target API set to: {self.base_url}")
                return True
            else:
                print("   ⚠️ Could not parse domain. Trying default fallback...")
                self.base_domain = "bet.betist1607.com" # Güncel fallback
                self.base_url = f"https://{self.base_domain}/getdata.php"
                return True
        except Exception as e:
            print(f"   ❌ Domain resolution failed: {e}")
            return False

    def _test_league_id(self, league_id):
        """Test if a league ID returns UFC/MMA content"""
        try:
            params = {
                'sec': 'ASIAN_LAYOUT',
                'subsec': 'REQUEST_GET_SCHEME_EVENTS',
                'league_id[]': league_id,
                'layout_schema_code': 'single_line_betist_1x2',
                'selected_date_period': 'null'
            }
            resp = requests.get(self.base_url, params=params, headers=self.headers, timeout=10, verify=False)
            
            if resp.status_code != 200:
                return False
            
            # Check if response contains UFC/MMA keywords
            text = resp.text.lower()
            # Look for fighter names or UFC/MMA keywords
            ufc_indicators = ['ufc', 'mma', 'mixed martial', 'cont_odds_row']
            
            for indicator in ufc_indicators:
                if indicator in text:
                    # Also check if there's actual content (not empty league)
                    if 'cont_odds_row' in text or len(resp.text) > 500:
                        print(f"      ✅ League ID {league_id} appears valid (found '{indicator}')")
                        return True
            
            return False
        except Exception as e:
            print(f"      ⚠️ Test failed for ID {league_id}: {e}")
            return False
    
    def find_ufc_league_id(self):
        """Sitedeki UFC/MMA liginin güncel ID'sini dinamik olarak bulur"""
        print("   🔎 Searching for active UFC League ID...")
        
        if not self.base_url:
            print("   ❌ Base URL not set")
            return False
        
        # İmport config for known IDs
        try:
            import config
            potential_ids = config.BETIST_KNOWN_LEAGUE_IDS
        except:
            potential_ids = ["41875249", "41875250", "41875251", "30582", "41875252"]
        
        print(f"   🧪 Testing {len(potential_ids)} known league IDs...")
        
        # Try known IDs first (fast path)
        for test_id in potential_ids:
            if self._test_league_id(test_id):
                self.active_league_id = test_id
                print(f"   ✅ Found valid UFC League ID: {test_id}")
                return True
        
        # If none of the known IDs work, try to discover new ones
        print("   🔍 Known IDs failed. Attempting discovery...")
        
        # Try sequential IDs around the known ones (brute force)
        base_id = 41875249
        for offset in range(-10, 20):  # Try IDs around the base
            test_id = str(base_id + offset)
            if test_id not in potential_ids:  # Skip already tested
                if self._test_league_id(test_id):
                    self.active_league_id = test_id
                    print(f"   🎯 Discovered new UFC League ID: {test_id}")
                    print(f"   💡 Consider adding {test_id} to config.BETIST_KNOWN_LEAGUE_IDS")
                    return True
        
        print("   ❌ Could not find valid UFC League ID")
        print("   💡 The betting site may have changed its structure")
        return False

    def fetch_event_list(self):
        """Fetch fight list from betting site"""
        if not self.base_url:
            print("   ❌ Base URL not configured")
            return
        
        if not self.active_league_id:
            print("   ❌ No active league ID set")
            return
        
        print(f"   📡 Fetching Odds from {self.base_domain} (League ID: {self.active_league_id})...")
        
        params = {
            'sec': 'ASIAN_LAYOUT',
            'subsec': 'REQUEST_GET_SCHEME_EVENTS',
            'league_id[]': self.active_league_id,
            'layout_schema_code': 'single_line_betist_1x2',
            'selected_date_period': 'null'
        }
        try:
            resp = requests.get(self.base_url, params=params, headers=self.headers, timeout=15, verify=False)
            
            # --- DEBUG: Sitede ne var? ---
            # Sitedeki isimleri ekrana basalım ki ID yanlış mı yoksa maç mı yok anlayalım
            soup = BeautifulSoup(resp.text, 'html.parser')
            rows = soup.find_all('tbody', class_='cont_odds_row')
            
            found_names = []
            
            count = 0
            for row in rows:
                try:
                    name_span = row.find('span', class_='not_favorite_part')
                    if not name_span: continue
                    full_name_text = name_span.get_text(strip=True)
                    found_names.append(full_name_text)
                    
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
            
            if count > 0:
                print(f"   ✅ Successfully indexed {count} fight(s)")
                print(f"   📋 Fighters mapped: {len(self.fighter_to_id)}")
            else:
                print("   ⚠️ No fights found in this League ID")
                print(f"   🔍 Response status: {resp.status_code}")
                print(f"   🔍 Response length: {len(resp.text)} bytes")
                if len(resp.text) < 1000:
                    print(f"   🔍 Full response: {resp.text}")
                else:
                    print(f"   🔍 Response snippet: {resp.text[:500]}...")
                
            if len(found_names) > 0:
                print("   📋 Available Fights on Site:")
                for name in found_names[:5]: # İlk 5 maçı göster
                    print(f"      - {name}")
                    
        except Exception as e:
            print(f"   ❌ List fetch failed: {e}")

    def clean_name(self, name):
        return " ".join(name.lower().split())

    def get_event_id_smart(self, f1, f2):
        """Improved fighter name matching with confidence scoring"""
        f1_clean = self.clean_name(f1)
        f2_clean = self.clean_name(f2)
        
        # Import config for cutoff
        try:
            import config
            primary_cutoff = config.FUZZY_MATCH_CUTOFF
            relaxed_cutoff = config.FUZZY_MATCH_CUTOFF_RELAXED
        except:
            primary_cutoff = 0.8
            relaxed_cutoff = 0.7
        
        # 1. Exact match (case-insensitive)
        for db_name, ev_id in self.fighter_to_id.items():
            if f1_clean == db_name or f2_clean == db_name:
                print(f"      🎯 Exact match: {f1} -> {db_name}")
                return ev_id
        
        # 2. Full name token match (all words must match)
        for db_name, ev_id in self.fighter_to_id.items():
            f1_parts = set(f1_clean.split())
            db_parts = set(db_name.split())
            
            # All words from f1 must be in db_name
            if f1_parts.issubset(db_parts) or db_parts.issubset(f1_parts):
                print(f"      🎯 Full token match: {f1} -> {db_name}")
                return ev_id
        
        # 3. Fuzzy Match (high cutoff)
        all_db_names = list(self.fighter_to_id.keys())
        match = difflib.get_close_matches(f1_clean, all_db_names, n=1, cutoff=primary_cutoff)
        if match:
            confidence = difflib.SequenceMatcher(None, f1_clean, match[0]).ratio()
            print(f"      🔍 Fuzzy match: {f1} -> {match[0]} (confidence: {confidence:.2f})")
            return self.fighter_to_id[match[0]]
        
        # Try f2
        match2 = difflib.get_close_matches(f2_clean, all_db_names, n=1, cutoff=primary_cutoff)
        if match2:
            confidence = difflib.SequenceMatcher(None, f2_clean, match2[0]).ratio()
            print(f"      🔍 Fuzzy match: {f2} -> {match2[0]} (confidence: {confidence:.2f})")
            return self.fighter_to_id[match2[0]]
        
        # 4. Relaxed fuzzy match (last resort)
        match_relaxed = difflib.get_close_matches(f1_clean, all_db_names, n=1, cutoff=relaxed_cutoff)
        if match_relaxed:
            confidence = difflib.SequenceMatcher(None, f1_clean, match_relaxed[0]).ratio()
            print(f"      ⚠️ Relaxed match: {f1} -> {match_relaxed[0]} (confidence: {confidence:.2f})")
            return self.fighter_to_id[match_relaxed[0]]
        
        print(f"      ❌ No match found for: {f1} vs {f2}")
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
    urllib3.disable_warnings() 
    
    print("--- 💰 STEP 3: ODDS HUNTER (DEBUG MODE) ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except: 
        print(f"❌ '{INPUT_FILE}' not found.")
        return

    engine = BetistEngine()
    
    if not engine.resolve_current_domain():
        print("❌ Critical: Cannot find Betist domain.")
        return

    engine.find_ufc_league_id()
    engine.fetch_event_list()
    
    found_count = 0
    for fight in data:
        f1, f2 = fight['fighters'][0], fight['fighters'][1]
        print(f"\n🔍 Hunting Odds: {f1} vs {f2}")
        
        ev_id = engine.get_event_id_smart(f1, f2)
        if ev_id:
            print(f"   ✅ ID Found: {ev_id}")
            odds = engine.fetch_market_details(ev_id, f1, f2)
            if odds:
                fight['betist_odds'] = odds
                found_count += 1
                print(f"      📊 Markets Found: {len(odds)} categories")
            else:
                print("      ⚠️ Markets empty.")
        else:
            print("      ❌ Match not found on betting site (Might be too far in future).")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n📁 Odds data saved to '{OUTPUT_FILE}'. Matches: {found_count}/{len(data)}")

if __name__ == "__main__":
    main()