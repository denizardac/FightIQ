import requests
from bs4 import BeautifulSoup
import json
import re
import difflib
import time
import sys
import os
import logging
import urllib3

# Suppress insecure request warnings for Betist
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path
from core.odds_converter import normalize_odds  # P0 FINAL: Universal Format
try:
    import core.config as config
except ImportError:
    # Use fallback constants if config missing
    class config:
        FUZZY_MATCH_CUTOFF_MEDIUM = 0.75
        FUZZY_MATCH_CUTOFF_LOW = 0.6

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
INPUT_FILE = get_data_path("2_data.json")
OUTPUT_FILE = get_data_path("2_data_with_odds.json")

# Betist configuration (Primary Source)
BETIST_REDIRECT_URL = "https://cutt.ly/zrIT6E9d"

# BestFightOdds configuration (Secondary Source - FALLBACK)
BESTFIGHTODDS_BASE = "https://www.bestfightodds.com"

# Setup logging
logger = logging.getLogger("FightIQ.OddsHunter")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Windows console UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass


# ==========================================
# PRIMARY SOURCE: BETIST ENGINE
# ==========================================

class BetistEngine:
    """Primary odds source - Dynamic Turkish betting site (API-BASED)"""
    
    def __init__(self):
        self.fighter_to_id = {} 
        self.base_domain = None
        self.base_url = None
        self.active_league_id = None
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'https://bet.betist1630.com/'
        }
        self.session.headers.update(self.headers)

    def resolve_current_domain(self):
        """Scan Betist domains directly (cutt.ly redirect is dead)"""
        logger.info("Scanning for active Betist domain...")
        import urllib3
        urllib3.disable_warnings()
        # Try a range of known domains
        for num in range(1630, 1660):
            domain = f"bet.betist{num}.com"
            try:
                r = self.session.get(
                    f"https://{domain}/",
                    timeout=6, allow_redirects=True, verify=False
                )
                if r.status_code == 200:
                    self.base_domain = domain
                    self.base_url = f"https://{domain}/getdata.php"
                    self.session.headers['Referer'] = f"https://{domain}/"
                    logger.info(f"Active Betist domain found: {domain}")
                    return True
            except Exception:
                continue
        logger.error("No active Betist domain found in range 1630-1659")
        return False

    def find_ufc_league_id(self):
        """Use the confirmed UFC League ID from network analysis"""
        # The browser agent confirmed 41875249 is the correct ID for UFC
        self.active_league_id = "41875249"
        logger.info(f"Using confirmed UFC League ID: {self.active_league_id}")
        return True

    def fetch_event_list(self):
        """Fetch and index fights from Betist API (HTML Parsing)"""
        if not self.base_url or not self.active_league_id:
            logger.error("Betist not properly initialized")
            return False
        
        logger.info(f"Fetching odds from {self.base_domain} (League: {self.active_league_id})")
        
        params = {
            'sec': 'ASIAN_LAYOUT',
            'subsec': 'REQUEST_GET_SCHEME_EVENTS',
            'league_id[]': self.active_league_id,
            'layout_schema_code': 'single_line_betist_1x2',
            'start': '',
            'end': '',
            'selected_date_period': 'null'
        }
        
        try:
            resp = self.session.get(self.base_url, params=params, timeout=15, verify=False)
            
            # The API returns HTML fragments, not pure JSON
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            count = 0
            
            # Find all event rows or cells that usually contain the ID
            # Based on debug: onClick="openAdditional(12294343);" inside a td with class m-bet-grid__cell_count
            click_cells = soup.find_all('td', class_='m-bet-grid__cell_count')
            
            for cell in click_cells:
                onclick_text = cell.get('onclick', '')
                if 'openAdditional' in onclick_text:
                    match = re.search(r'openAdditional\(\s*(\d+)\s*\)', onclick_text)
                    if match:
                        event_id = match.group(1)
                        
                        # Now find the event name. It's usually in the same row or a related structure.
                        # In the HTML structure: 
                        # <tr class="cont_odds_row_top"> ... <td class="cont_part_row"> <span class="not_favorite_part">Name - Name</span> ... </tr>
                        # The count cell is in the same row.
                        
                        row = cell.find_parent('tr')
                        if row:
                            name_span = row.find('span', class_='not_favorite_part')
                            if name_span:
                                raw_name = name_span.get_text().strip()
                                
                                # Clean and split name
                                fighters = raw_name.split(' - ')
                                if len(fighters) < 2:
                                    fighters = raw_name.split(' v ')
                                
                                if len(fighters) >= 2:
                                    for f in fighters:
                                        clean_f = self.clean_name(f)
                                        if len(clean_f) > 3:
                                            self.fighter_to_id[clean_f] = event_id
                                    count += 1
                                    
            if count > 0:
                logger.info(f"Betist indexed {count} fights via HTML scan ({len(self.fighter_to_id)} fighters)")
                return True
            else:
                logger.warning("No fights found in Betist HTML response")
                return False
                
        except Exception as e:
            logger.error(f"Betist fetch failed: {e}")
            return False

    def clean_name(self, name):
        """Normalize fighter names"""
        return " ".join(name.lower().split())

    def get_event_id_smart(self, f1, f2):
        """Match fighter names to event IDs using fuzzy matching"""
        f1_clean = self.clean_name(f1)
        f2_clean = self.clean_name(f2)
        
        # Exact match
        for db_name, ev_id in self.fighter_to_id.items():
            if f1_clean == db_name or f2_clean == db_name:
                logger.debug(f"Exact match: {f1} -> {db_name}")
                return ev_id
        
        # Fuzzy match
        all_names = list(self.fighter_to_id.keys())
        if not all_names: return None
        
        match = difflib.get_close_matches(f1_clean, all_names, n=1, cutoff=config.FUZZY_MATCH_CUTOFF_MEDIUM)
        if match:
            logger.debug(f"Fuzzy match: {f1} -> {match[0]}")
            return self.fighter_to_id[match[0]]
        
        match = difflib.get_close_matches(f2_clean, all_names, n=1, cutoff=config.FUZZY_MATCH_CUTOFF_MEDIUM)
        if match:
            logger.debug(f"Fuzzy match: {f2} -> {match[0]}")
            return self.fighter_to_id[match[0]]
        
        return None

    def fetch_market_detail(self, event_id):
        """Fetch comprehensive betting markets for specific event from API (HTML embedded JSON)"""
        params = {
            'sec': 'ASIAN_LAYOUT',
            'subsec': 'REQUEST_GET_ADDITIONAL_MARKETS',
            'event_id': event_id,
            'selected_date_period': 'null'
        }
        
        try:
            resp = self.session.get(self.base_url, params=params, timeout=10, verify=False)
            
            # Use BeautifulSoup to parse the HTML response
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            odds = {}
            
            # Find all 'a' tags with a 'rev' attribute which contains the JSON data
            anchors = soup.find_all('a', rev=True)
            
            for a in anchors:
                try:
                    rev_data = a.get('rev')
                    if not rev_data: continue
                    
                    # Handle multi-valued attributes (BS4 sometimes returns list)
                    if isinstance(rev_data, list):
                        rev_data = " ".join(rev_data)
                    
                    # Fix HTML entities in JSON string (e.g. &quot; -> ")
                    rev_data = rev_data.replace('&quot;', '"').replace('&amp;', '&')
                    
                    try:
                        data = json.loads(rev_data)
                    except json.JSONDecodeError:
                        continue
                    
                    market_name = data.get('type_title', '').strip() or data.get('scope_title', 'Unknown').strip()
                    
                    # Handle outcome name safely (beton_val can be int 0)
                    beton_val = data.get('beton_val')
                    if beton_val and str(beton_val) != '0':
                        outcome_name = str(beton_val).strip()
                    else:
                        outcome_name = str(data.get('beton', '')).strip()

                    odd_value = data.get('odds')
                    
                    # Normalize Market Name
                    if market_name == "Kazanır":
                        market_name = "Moneyline"
                    elif market_name == "1x2":
                        market_name = "Moneyline"
                        
                    if market_name and outcome_name and odd_value:
                        if market_name not in odds:
                            odds[market_name] = {}
                            
                        # Try to normalize odds
                        try:
                            odds[market_name][outcome_name] = normalize_odds(float(odd_value), 'decimal')
                        except Exception:
                            # Fallback to raw float if normalization fails
                            odds[market_name][outcome_name] = float(odd_value)
                            
                except Exception:
                    continue
            
            return odds
            
        except Exception as e:
            logger.debug(f"Market detail fetch failed for event {event_id}: {e}")
            return {}


# ==========================================
# SECONDARY SOURCE: BESTFIGHTODDS ENGINE
# ==========================================

class BestFightOddsEngine:
    """Secondary odds source - Aggregator of major sportsbooks"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.odds_data = {}
        self.line_movement_data = {}

    def clean_name(self, name):
        """Normalize fighter name for consistent dict lookups."""
        return " ".join(name.lower().split())

    def fetch_odds(self):
        """Scrape odds from BestFightOdds.com - FIXED to parse table structure correctly"""
        logger.info("Fetching from BestFightOdds.com (secondary source)...")
        
        try:
            resp = requests.get(BESTFIGHTODDS_BASE, headers=self.headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find all odds tables directly
            # This is more robust than relying on header -> table traversal
            tables = soup.find_all('table', class_='odds-table')
            
            count = 0
            
            for table in tables:
                # Try to find associated header for Event URL (best effort)
                # The header is usually the previous sibling or previous 'table-header' div
                current_event_url = None
                try:
                    # Look for the preceding table-header
                    prev_header = table.find_previous('div', class_='table-header')
                    if prev_header:
                        event_link = prev_header.find('a', href=re.compile(r'/events/'))
                        if event_link:
                            href = event_link.get('href')
                            if href:
                                current_event_url = BESTFIGHTODDS_BASE + href if href.startswith('/') else href
                except:
                    pass # Ignore header errors, we want the ODDS
                
                rows = table.find_all('tr')
                i = 0
                while i < len(rows) - 1:
                    try:
                        row1 = rows[i]
                        row2 = rows[i+1]
                        
                        # Validate fighter pair [P0: Must have fighter links]
                        link1 = row1.find('a', href=re.compile(r'/fighters/'))
                        link2 = row2.find('a', href=re.compile(r'/fighters/'))
                        
                        if not (link1 and link2):
                            i += 1
                            continue
                            
                        # Extract Names
                        f1_name = link1.get_text(strip=True)
                        f2_name = link2.get_text(strip=True)
                        
                        # Extract Odds using simplified logic
                        # Helper to get first odds from row
                        def get_odds_from_row(r):
                            # Search td, th and span for american odds
                            for cell in r.find_all(['td', 'th', 'span']):
                                txt = cell.get_text(strip=True)
                                m = re.search(r'([+-]\d{3,5})', txt)
                                if m: return m.group(1)
                            return None
                            
                        odds1 = get_odds_from_row(row1)
                        odds2 = get_odds_from_row(row2)
                        
                        if odds1 and odds2:
                            matchup_key = f"{f1_name} vs {f2_name}".lower()
                            
                            self.odds_data[matchup_key] = {
                                "fighter1": f1_name,
                                "fighter2": f2_name,
                                "source": "BestFightOdds",
                                "event_url": current_event_url,
                                "markets": {
                                    "moneyline": {
                                        "fighter_a": normalize_odds(odds1, 'american'),
                                        "fighter_b": normalize_odds(odds2, 'american')
                                    }
                                }
                            }
                            count += 1
                        
                        i += 2
                    except Exception as e:
                        # logger.warning(f"Row parsing warning: {e}")
                        i += 1
            
            logger.info(f"BFO Scrape Complete. Found {count} matchups.")
            
            if count > 0:
                logger.info(f"BestFightOdds: Extracted {count} matchups with odds")
                return True
            else:
                logger.warning("BestFightOdds: No odds extracted")
                return False
                        

            
            if count > 0:
                logger.info(f"BestFightOdds: Extracted {count} matchups with odds")
                # NOTE: Line movement is on event detail pages, not homepage
                return True
            else:
                logger.warning("BestFightOdds: No odds extracted")
                return False
                
        except Exception as e:
            logger.error(f"BestFightOdds fetch failed: {e}")
            return False

    def get_odds_for_fight(self, f1, f2):
        """Match fighters to scraped odds"""
        f1_clean = " ".join(f1.lower().split())
        f2_clean = " ".join(f2.lower().split())
        
        # Check all indexed matchups
        for matchup_key, data in self.odds_data.items():
            if (f1_clean in matchup_key or f2_clean in matchup_key):
                logger.debug(f"BestFightOdds match found for {f1} vs {f2}")
                return data
        
        # Fuzzy matching as fallback
        all_matchups = list(self.odds_data.keys())
        search_key = f"{f1_clean} vs {f2_clean}"
        match = difflib.get_close_matches(search_key, all_matchups, n=1, cutoff=config.FUZZY_MATCH_CUTOFF_LOW)
        
        if match:
            logger.debug(f"BestFightOdds fuzzy match: {match[0]}")
            return self.odds_data[match[0]]
        
        return None

    def scrape_line_movement(self, soup):
        """
        Scrape line movement from event detail page.
        Target: #event-swing-container data-moves attribute (contains JSON)
        """
        logger.info("Scraping line movement data from event detail...")
        
        try:
            # 1. Find the container with the data
            container = soup.find(id="event-swing-container")
            if not container or not container.has_attr('data-moves'):
                # Try finding by class if ID not found, just in case
                container = soup.find("div", class_="event-swing-container")
            
            if not container or not container.has_attr('data-moves'):
                # logger.warning("Line movement container (event-swing-container) not found")
                return

            # 2. Parse the JSON data
            raw_json = container['data-moves']
            try:
                moves_data = json.loads(raw_json)
            except json.JSONDecodeError:
                logger.error("Failed to parse data-moves JSON")
                return

            # 3. Extract "Change since opening" data
            target_data = None
            for item in moves_data:
                # Look for name="Change since opening" (case insensitive check)
                if item.get("name") and "opening" in item.get("name").lower():
                    target_data = item.get("data", [])
                    break
            
            if not target_data and moves_data:
                # Fallback to first item if explicit name match fails
                target_data = moves_data[0].get("data", [])

            # 4. Store in dictionary
            if target_data:
                count = 0
                for entry in target_data:
                    if isinstance(entry, list) and len(entry) >= 2:
                        fighter_name = entry[0]
                        pct_value = entry[1] # Integer like -50 or 22
                        
                        # Format as string with sign
                        sign = "+" if pct_value > 0 else ""
                        formatted_pct = f"{sign}{pct_value}%"
                        
                        self.line_movement_data[self.clean_name(fighter_name)] = formatted_pct
                        count += 1
                
                logger.info(f"Successfully extracted line movement for {count} fighters")
            
        except Exception as e:
            logger.warning(f"Failed to scrape line movement: {e}")
            
    def _unused_legacy_scraper(self):
        # Placeholder to ensure indentation alignment if needed
        pass

    def fetch_event_detail_page(self, event_url):
        """
        Fetch specific event detail page for prop bets.
        
        Args:
            event_url: Relative URL like '/events/ufc-324-3456'
        
        Returns:
            BeautifulSoup object or None if failed
        """
        if not event_url:
            return None

        # Guard against already-absolute URLs (would produce double base otherwise)
        if event_url.startswith("http"):
            full_url = event_url
        else:
            full_url = BESTFIGHTODDS_BASE + event_url
        logger.debug(f"Fetching event detail: {full_url}")
        
        try:
            resp = requests.get(full_url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'html.parser')
            else:
                logger.warning(f"Event detail page returned status {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch event detail page: {e}")
            return None

    def scrape_props_from_detail_page(self, soup):
        """
        Extract Method of Victory and Rounds props from event detail page.
        
        Returns:
            dict with 'method_of_victory' and 'total_rounds' props (or empty dict)
        """
        if not soup:
            return {}
        
        props = {}
        
        try:
            # Look for prop sections
            # Common identifiers: "props", "method of victory", "total rounds"
            
            # Strategy: Find tables or sections with prop headers
            prop_keywords = [
                (r'method\s+of\s+victory', 'method_of_victory'),
                (r'finish', 'method_of_victory'),
                (r'total\s+rounds', 'total_rounds'),
                (r'over.*under', 'total_rounds')
            ]
            
            for pattern, prop_key in prop_keywords:
                # Find header element
                header = soup.find(string=re.compile(pattern, re.I))
                if header:
                    # Get parent table or container
                    container = header.find_parent(['table', 'div', 'section'])
                    if container:
                        # Extract odds from this section
                        # Look for american odds patterns (+XXX or -XXX)
                        odds_cells = container.find_all(['td', 'span', 'div'])
                        
                        for cell in odds_cells:
                            text = cell.get_text(strip=True)
                            # Match american odds
                            odds_match = re.search(r'([+-]\d{3,4})', text)
                            if odds_match:
                                odds_str = odds_match.group(1)
                                
                                # Try to identify what type (KO, Sub, Decision, Over, Under)
                                cell_text_lower = text.lower()
                                
                                if prop_key == 'method_of_victory':
                                    if 'ko' in cell_text_lower or 'tko' in cell_text_lower or 'knockout' in cell_text_lower:
                                        props.setdefault('method_of_victory', {})['KO/TKO'] = normalize_odds(odds_str, 'american')
                                    elif 'sub' in cell_text_lower:
                                        props.setdefault('method_of_victory', {})['Submission'] = normalize_odds(odds_str, 'american')
                                    elif 'dec' in cell_text_lower or 'decision' in cell_text_lower:
                                        props.setdefault('method_of_victory', {})['Decision'] = normalize_odds(odds_str, 'american')
                                
                                elif prop_key == 'total_rounds':
                                    if 'over' in cell_text_lower:
                                        props.setdefault('total_rounds', {})['Over_2.5'] = normalize_odds(odds_str, 'american')
                                    elif 'under' in cell_text_lower:
                                        props.setdefault('total_rounds', {})['Under_2.5'] = normalize_odds(odds_str, 'american')
            
            if props:
                logger.debug(f"Scraped props: {list(props.keys())}")
            else:
                logger.debug("No props found on event detail page")
        
        except Exception as e:
            logger.warning(f"Failed to scrape props: {e}")
        
        return props

    def get_line_movement_for_fighter(self, fighter_name):
        """Get line movement percentage for a specific fighter"""
        fighter_clean = " ".join(fighter_name.lower().split())
        
        # Exact match
        if fighter_clean in self.line_movement_data:
            return self.line_movement_data[fighter_clean]
        
        # Fuzzy match
        for stored_name, percentage in self.line_movement_data.items():
            if fighter_clean in stored_name or stored_name in fighter_clean:
                return percentage
        
        return None

# ==========================================
# DUAL-SOURCE ORCHESTRATOR
# ==========================================

def get_odds_dual_source(f1, f2, betist_engine, bfo_engine, fight_data=None):
    """
    Attempt to get odds from both sources with priority fallback.
    
    P0 CRITICAL RULE: NO SIMULATED ODDS. Only real market data.
    """
    odds_result = {
        "source": None,
        "odds": None,
        "confidence": "unknown"
    }
    
    # PRIMARY: Try Betist first
    betist_succeeded = False
    try:
        event_id = betist_engine.get_event_id_smart(f1, f2)
        if event_id:
            markets = betist_engine.fetch_market_detail(event_id)
            if markets:
                odds_result["source"] = "Betist (Live)"
                odds_result["odds"] = markets
                odds_result["confidence"] = "high"
                logger.info(f"✅ Betist odds found for {f1} vs {f2}")
                betist_succeeded = True
    except Exception as e:
        logger.warning(f"Betist failed for {f1} vs {f2}: {e}")

    # SECONDARY: BFO — used as fallback OR to enrich Betist with line movement data
    try:
        bfo_data = bfo_engine.get_odds_for_fight(f1, f2)
        if bfo_data:
            bfo_markets = bfo_data.get("markets", {})
            event_url = bfo_data.get("event_url")
            
            line_movement = None
            props = None
            
            if event_url:
                logger.debug(f"Fetching BFO event detail: {event_url}")
                detail_soup = bfo_engine.fetch_event_detail_page(event_url)
                if detail_soup:
                    # Scrape line movement
                    bfo_engine.scrape_line_movement(detail_soup)
                    line_movement_f1 = bfo_engine.get_line_movement_for_fighter(f1)
                    line_movement_f2 = bfo_engine.get_line_movement_for_fighter(f2)
                    
                    if line_movement_f1 or line_movement_f2:
                        line_movement = {
                            "fighter_a": line_movement_f1,
                            "fighter_b": line_movement_f2
                        }
                    
                    # Scrape props just in case Betist missed them
                    props = bfo_engine.scrape_props_from_detail_page(detail_soup)

            # Enrich Betist result with BFO line movement (if Betist succeeded)
            if betist_succeeded:
                if line_movement:
                    odds_result["odds"]["line_movement"] = line_movement
                    logger.info(f"BFO line movement enriched Betist data for {f1} vs {f2}")
                return odds_result
            
            # If Betist failed, use BFO as primary source
            odds_result["source"] = "BestFightOdds (Aggregator)"
            
            # P0 FIX: Ensure odds are mapped to the correct fighter index (f1 vs f2)
            # bfo_markets has 'fighter_a' (corresponding to bfo_data['fighter1']) 
            # and 'fighter_b' (corresponding to bfo_data['fighter2'])
            
            bfo_f1 = bfo_data.get("fighter1")
            bfo_f2 = bfo_data.get("fighter2")
            
            moneyline = bfo_markets.get("moneyline", {})
            bfo_odds_a = moneyline.get("fighter_a")
            bfo_odds_b = moneyline.get("fighter_b")
            
            final_moneyline = {}
            
            # Helper to check name match
            def is_match(n1, n2):
                if not n1 or not n2: return False
                return n1.lower() in n2.lower() or n2.lower() in n1.lower()
            
            # Map BFO fighters to Requested fighters (f1, f2)
            if is_match(bfo_f1, f1):
                # Direct match: f1 is fighter_a
                final_moneyline["fighter_a"] = bfo_odds_a
                final_moneyline["fighter_b"] = bfo_odds_b
                logger.debug(f"Direct match: {f1} -> {bfo_f1}")
            elif is_match(bfo_f1, f2):
                # Swapped: f1 is fighter_b
                final_moneyline["fighter_a"] = bfo_odds_b # f1 gets BFO's fighter_b odds
                final_moneyline["fighter_b"] = bfo_odds_a # f2 gets BFO's fighter_a odds
                logger.debug(f"Swapped match: {f1} -> {bfo_f2} (Original Top: {bfo_f1})")
            else:
                # Fallback (Name mismatch or complex fuzzy), trust original order if unknown
                # Or try matching the other way
                 if is_match(bfo_f2, f1):
                     final_moneyline["fighter_a"] = bfo_odds_b
                     final_moneyline["fighter_b"] = bfo_odds_a
                 else:
                     # Hail mary: Assume order is correct
                     final_moneyline["fighter_a"] = bfo_odds_a
                     final_moneyline["fighter_b"] = bfo_odds_b
                     logger.warning(f"Ambiguous mapping for {f1}/{f2} vs {bfo_f1}/{bfo_f2}")

            # Reconstruct the markets object
            odds_result["odds"] = {
                "moneyline": final_moneyline
            }
            # Add other markets if they exist (props etc) passed through? 
            # BFO usually only has moneyline reliably in this path.
            
            odds_result["confidence"] = "medium"
            
            if line_movement:
                odds_result["odds"]["line_movement"] = line_movement
            if props:
                odds_result["odds"]["props"] = props
            
            logger.info(f"⚠️ BestFightOdds fallback used for {f1} vs {f2}")
            return odds_result
            
    except Exception as e:
        logger.warning(f"BestFightOdds failed for {f1} vs {f2}: {e}")

    
    # CRITICAL: Both sources failed - DO NOT SIMULATE
    logger.error(f"❌ BOTH SOURCES FAILED for {f1} vs {f2}")
    logger.error("❌ NO ODDS DATA AVAILABLE - Will skip betting analysis for this fight")
    odds_result["source"] = "UNAVAILABLE"
    odds_result["odds"] = {}
    odds_result["confidence"] = "none"
    
    return odds_result

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    logger.info("="*60)
    logger.info("ODDS HUNTER V2.0 - DUAL-SOURCE SCRAPING (P0 UPGRADE)")
    logger.info("="*60)
    logger.info("PRIMARY: Betist (Turkish, Live)")
    logger.info("SECONDARY: BestFightOdds.com (Multi-sportsbook Aggregator)")
    logger.info("CRITICAL RULE: NO SIMULATED ODDS EVER")
    logger.info("="*60)
    
    # Load input data
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            fights_data = json.load(f)
        logger.info(f"Loaded {len(fights_data)} fights from {INPUT_FILE}")
    except Exception as e:
        logger.critical(f"Failed to load input file: {e}")
        return
    
    # Initialize PRIMARY source (Betist)
    betist = BetistEngine()
    betist_ready = False
    
    if betist.resolve_current_domain():
        if betist.find_ufc_league_id():
            if betist.fetch_event_list():
                betist_ready = True
                logger.info("✅ Betist (PRIMARY) initialized successfully")
    
    if not betist_ready:
        logger.warning("⚠️ Betist (PRIMARY) initialization failed")
    
    # Initialize SECONDARY source (BestFightOdds)
    bfo = BestFightOddsEngine()
    bfo_ready = bfo.fetch_odds()
    
    if bfo_ready:
        logger.info("✅ BestFightOdds (SECONDARY) initialized successfully")
    else:
        logger.warning("⚠️ BestFightOdds (SECONDARY) initialization failed")
    
    # Check if we have ANY source available
    if not betist_ready and not bfo_ready:
        logger.critical("❌ CRITICAL: ALL ODDS SOURCES FAILED")
        logger.critical("❌ Cannot proceed with odds enrichment")
        logger.critical("❌ Saving input data as-is (no odds added)")
        
        # Save input as output to allow pipeline to continue
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(fights_data, f, indent=2, ensure_ascii=False)
        
        logger.warning("Pipeline will continue but betting analysis will be incomplete")
        return
    
    # Process each fight with dual-source logic
    logger.info("="*60)
    logger.info("PROCESSING FIGHTS WITH DUAL-SOURCE LOGIC")
    logger.info("="*60)
    
    enriched_data = []
    success_count = 0
    partial_count = 0
    fail_count = 0
    
    for i, fight in enumerate(fights_data, 1):
        fighters = fight.get('fighters', [])
        
        if len(fighters) != 2:
            logger.warning(f"Fight {i}: Invalid fighter count, skipping")
            enriched_data.append(fight)
            continue
        
        f1, f2 = fighters[0], fighters[1]
        logger.info(f"Fight {i}/{len(fights_data)}: {f1} vs {f2}")
        
        # Get odds from dual sources (pass fight data for props)
        odds_result = get_odds_dual_source(f1, f2, betist, bfo, fight)
        
        # NEW SCHEMA: market_data instead of betist_odds
        fight['market_data'] = odds_result['odds']
        fight['odds_source_primary'] = odds_result['source']
        fight['odds_confidence'] = odds_result['confidence']
        
        if odds_result['confidence'] == 'high':
            success_count += 1
        elif odds_result['confidence'] in ['medium', 'low']:
            partial_count += 1
        else:
            fail_count += 1
        
        enriched_data.append(fight)
        time.sleep(0.5)  # Rate limiting
    
    # Save enriched data
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info("ODDS ENRICHMENT COMPLETE")
    logger.info(f"Total Fights: {len(fights_data)}")
    logger.info(f"✅ Full odds (Betist): {success_count}")
    logger.info(f"⚠️ Partial odds (BestFightOdds): {partial_count}")
    logger.info(f"❌ No odds: {fail_count}")
    logger.info(f"Saved to: {OUTPUT_FILE}")
    logger.info("="*60)
    
    # Return exit code based on success rate
    if success_count + partial_count > 0:
        logger.info("✅ Odds enrichment successful (at least partial data)")
        return 0 # Success
    else:
        logger.error("❌ No odds data obtained from any source")
        return 1  # Failure

if __name__ == "__main__":
    sys.exit(main() or 0)