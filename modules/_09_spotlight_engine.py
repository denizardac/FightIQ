import json
import random
import os
import requests
import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv
import urllib.parse
import time
import traceback


# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, get_output_path, MODULES_DIR
from core.naming import card_basename, versus_basename
from core.ufcstats_http import fetch as ufcstats_fetch

# Import config
try:
    import core.config as config
except ImportError:
    # P0: If config fails, we should crash rather than using stale defaults
    print("❌ FATAL: core/config.py not found. Cannot proceed.")
    sys.exit(1)


# --- IMPORT MODULES ---
# P0 FIX: Standard imports instead of dynamic importlib
try:
    from modules import _11_trend_hunter as TrendHunter
except ImportError as e:
    print(f"⚠️ Failed to import TrendHunter: {e}")
    TrendHunter = None

try:
    from modules import _03_odds_hunter as OddsHunterModule
except ImportError as e:
    print(f"⚠️ Failed to import OddsHunter: {e}")
    OddsHunterModule = None

try:
    from modules import _06_visual_engine as VisualEngine
except ImportError as e:
    print(f"❌ Error: VisualEngine not available - {e}")
    sys.exit(1)

try:
    from modules import _10_video_engine as VideoEngine
except ImportError as e:
    print(f"⚠️ Failed to import VideoEngine: {e}")
    VideoEngine = None

BetistEngine = OddsHunterModule.BetistEngine if OddsHunterModule else None


# --- CONFIG ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client = None
if GEMINI_KEY:
    try:
        client = genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        print(f"⚠️ GenAI Client Init Error: {e}")

DB_FILE = get_data_path("fighters_db.json")
HISTORY_FILE = get_data_path("spotlight_history.json")
OUTPUT_FILE = get_data_path("spotlight_ready.json")


from tenacity import retry, wait_exponential, stop_after_attempt

# --- HELPERS ---

@retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
def generate_with_retry(client, model_name, prompt):
    """Generates content with exponential backoff for 429 errors"""
    return client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )

def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f: 
            data = json.load(f)
            ninety_days_ago = datetime.now() - timedelta(days=config.SPOTLIGHT_HISTORY_DAYS)
            return [x for x in data if datetime.strptime(x['date'], "%Y-%m-%d") > ninety_days_ago]
    except Exception: return []

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: db = json.load(f)
        if "data" in db: return list(db["data"].keys()), db["data"]
        else: return list(db.keys()), db
    except Exception: return [], {}

def get_gemini_model():
    # Return initialized client
    return client

def scrape_fighter_detailed(url):
    if not url:
        return None
    resp = None
    for attempt in range(3):
        try:
            resp = ufcstats_fetch(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=12)
            if resp.status_code == 200:
                break
            resp = None
        except Exception:
            resp = None
            time.sleep(1)
    if not resp:
        return None
    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        data = {"url": url}
        
        # Name
        name_tag = soup.find('span', class_='b-content__title-highlight')
        data['name'] = name_tag.text.strip() if name_tag else "Unknown"
        
        # Record
        record_tag = soup.find('span', class_='b-content__title-record')
        data['wins'], data['losses'] = 0, 0
        if record_tag:
            rec_txt = record_tag.text.split(":")[1].strip() # "29-10-0"
            data['record'] = rec_txt
            parts = rec_txt.split("-")
            data['wins'] = int(parts[0])
            data['losses'] = int(parts[1])

        # Stats
        data['slpm'] = "0.00"
        data['str_acc'] = "0%"
        data['str_def'] = "0%"
        data['td_avg'] = "0.00"
        data['sub_avg'] = "0.0"
        data['stance'] = None
        data['nickname'] = ""
        
        # TALE OF THE TAPE: Height, Reach, Weight, DOB
        data['height'] = None
        data['weight'] = None
        data['reach'] = None
        data['dob'] = None
        data['age'] = None
        data['weight_class'] = None
        
        for item in soup.find_all('li', class_='b-list__box-list-item_type_block'):
            text = " ".join(item.text.split())
            if "SLpM:" in text: data['slpm'] = text.split("SLpM:")[1].strip()
            if "Str. Acc.:" in text: data['str_acc'] = text.split("Str. Acc.:")[1].strip()
            if "Str. Def.:" in text: data['str_def'] = text.split("Str. Def.:")[1].strip()
            if "TD Avg.:" in text: data['td_avg'] = text.split("TD Avg.:")[1].strip()
            if "Sub. Avg.:" in text: data['sub_avg'] = text.split("Sub. Avg.:")[1].strip()
            if "STANCE:" in text.upper():
                data['stance'] = text.split(":", 1)[-1].strip()
            
            # Tale of the Tape
            if "Height:" in text: data['height'] = text.split("Height:")[1].strip()
            if "Weight:" in text: data['weight'] = text.split("Weight:")[1].strip()
            if "Reach:" in text: data['reach'] = text.split("Reach:")[1].strip()
            if "DOB:" in text: 
                dob_str = text.split("DOB:")[1].strip()
                data['dob'] = dob_str
                # Calculate age
                try:
                    import datetime, re
                    dob_match = re.search(r'(\w+)\s+(\d+),\s+(\d{4})', dob_str)
                    if dob_match:
                        month_str, day, year = dob_match.groups()
                        dob_date = datetime.datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y")
                        today = datetime.datetime.now()
                        age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                        data['age'] = age
                except Exception:
                    pass

        nick_tag = soup.find('p', class_='b-content__Nickname')
        if nick_tag:
            data['nickname'] = nick_tag.get_text(strip=True)

        # Weight Class (derived from weight + gender detection)
        if data['weight']:
            try:
                weight_lbs = int(''.join(filter(str.isdigit, data['weight'])))
                
                # Determine base weight class
                if weight_lbs <= 125: base_class = "Flyweight"
                elif weight_lbs <= 135: base_class = "Bantamweight"
                elif weight_lbs <= 145: base_class = "Featherweight"
                elif weight_lbs <= 155: base_class = "Lightweight"
                elif weight_lbs <= 170: base_class = "Welterweight"
                elif weight_lbs <= 185: base_class = "Middleweight"
                elif weight_lbs <= 205: base_class = "Light Heavyweight"
                else: base_class = "Heavyweight"
                
                # GENDER DETECTION: ONLY mark as women's when explicit division
                # text appears in the fight history (not anywhere on the page —
                # site-wide navigation also contains "Women's" strings).
                is_womens = False
                if weight_lbs <= 145:
                    fight_table = soup.find('table', class_='b-fight-details__table')
                    if fight_table:
                        ftext = fight_table.get_text(separator=' ').lower()
                        # Strict markers: division/weight class labels used by UFC
                        womens_markers = [
                            "women's strawweight", "women's flyweight",
                            "women's bantamweight", "women's featherweight",
                            "wmma"
                        ]
                        if any(m in ftext for m in womens_markers):
                            is_womens = True

                if is_womens:
                    data['weight_class'] = f"Women's {base_class}"
                else:
                    data['weight_class'] = base_class
            except Exception:
                pass

        # RECENCY FILTER: ROW-WIDE REGEX (Date is in EVENT column)
        data['last_fight_year'] = None
        try:
            import re
            fight_table = soup.find('table', class_='b-fight-details__table')
            if fight_table and fight_table.find('tbody'):
                rows = fight_table.find('tbody').find_all('tr', class_='b-fight-details__table-row')
                
                # Check first 3 rows (skip "NEXT" fights)
                for row in rows[:3]:
                    row_text = row.get_text()
                    
                    # Skip if this is a "NEXT" fight (future/upcoming)
                    if 'next' in row_text.lower():
                        continue
                    
                    # REGEX: UFC date format "Jan. 25, 2025" or "Jul. 12, 2025"
                    date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.\s+(\d{1,2}),\s+(\d{4})'
                    match = re.search(date_pattern, row_text)
                    
                    if match:
                        year = int(match.group(3))  # Extract year (group 3)
                        data['last_fight_year'] = year
                        break  # Found most recent completed fight
        except Exception:
            pass
        
        # FALLBACK: High-tier fighter whitelist (if scraping fails)
        if not data['last_fight_year']:
            HIGH_TIER_ACTIVE = [
                'jon jones', 'alex pereira', 'islam makhachev', 'leon edwards', 
                'sean strickland', 'max holloway', 'ilia topuria', 'dricus du plessis',
                'tom aspinall', 'merab dvalishvili', 'belal muhammad', 'sean o malley',
                'alexander volkanovski', 'charles oliveira', 'justin gaethje', 'dustin poirier',
                'conor mcgregor', 'israel adesanya', 'robert whittaker', 'jiri prochazka',
                'alexander volkanovski', 'kamaru usman', 'colby covington', 'gilbert burns',
                'amanda nunes', 'valentina shevchenko', 'zhang weili', 'rose namajunas'
            ]
            if data['name'].lower() in HIGH_TIER_ACTIVE:
                data['last_fight_year'] = 2024  # Assume active

        return data
    except Exception: return None


def scraped_to_official_row(scraped):
    """Map spotlight scrape fields → Versus card UFC OFFICIAL strip keys."""
    if not scraped:
        return {}
    return {
        "SLpM": scraped.get("slpm") or "N/A",
        "Str_Acc": scraped.get("str_acc") or "N/A",
        "Str_Def": scraped.get("str_def") or "N/A",
        "TD_Avg": scraped.get("td_avg") or "N/A",
        "Sub_Avg": scraped.get("sub_avg") or "N/A",
    }


def prepare_versus_fighter_display(scraped, ai_side_stats=None):
    """Same tape/nickname fields as fight-week Versus cards."""
    ai_side_stats = ai_side_stats or {}
    nickname_page = (scraped.get("nickname") or "").strip()
    ol = (ai_side_stats.get("one_liner") or nickname_page or "").strip()
    if ol.upper() in ("FANTASY WAR", "N/A"):
        ol = nickname_page
    stance = scraped.get("stance") or "--"
    if stance and isinstance(stance, str):
        stance = stance.strip().title() if stance.strip() else "--"
    return {
        "name": scraped.get("name", "Unknown"),
        "record": scraped.get("record", "N/A"),
        "weight_class": scraped.get("weight_class", ""),
        "height": scraped.get("height") or "--",
        "reach": scraped.get("reach") or "--",
        "stance": stance,
        "age": scraped.get("age", "--"),
        "one_liner": ol,
    }


def parse_json_content(text):
    """Parses JSON from AI response, handling markdown blocks and list wrapping."""
    try:
        clean_text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean_text)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed[0]
        return parsed
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return None

# --- GENERATORS ---

def generate_standard_content(fighter_data):
    client = get_gemini_model()
    if not client: return None
    
    prompt = f"""
    ROLE: MMA Content Creator.
    TASK: Create content for UFC fighter: {fighter_data['name']}
    REAL STATS: Record: {fighter_data['record']}, SLpM: {fighter_data['slpm']}, Sub Avg: {fighter_data['sub_avg']}, TD Avg: {fighter_data['td_avg']}
    
    INSTRUCTION: Estimate 'card_stats' (0-100) based on REAL STATS.
    - High SLpM (>4.0) -> High Power/Stamina.
    - High Sub Avg (>0.5) -> High Grappling/Technique.
    - High Wins -> High Technique.
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "High-energy text. Focus on nickname/skill. End with question. Max 280 chars.",
        "stat_reply": "A 'Did You Know' tweet about their style. Max 280 chars.",
        "card_stats": {{ "power": "Est(0-100)", "grappling": "Est(0-100)", "stamina": "Est(0-100)", "chin": "Est(0-100)", "technique": "Est(0-100)", "one_liner": "3-5 word cool description" }},
        "video_script": "12-second hype script, max 35 words. No AI mentions. Punchy, energetic. Start with 'This is...'"
    }}
    """
    try:
        resp = generate_with_retry(client, config.GEMINI_MODELS[0], prompt)
        return parse_json_content(resp.text)
    except Exception as e:
        print(f"Error GenStandard: {e}")
        return None

def generate_violence_content(fighter_data):
    # Calculate Violence Score
    try:
        slpm = float(fighter_data.get('slpm', 0))
        wins = fighter_data.get('wins', 0)
        score = min(99, int((slpm * 10) + (wins * 0.5)))
    except Exception: score = 75

    client = get_gemini_model()
    if not client: return None

    prompt = f"""
    ROLE: The 'Just Bleed' God.
    TASK: Create VIOLENCE RATING content for: {fighter_data['name']}
    REAL STATS: SLpM: {fighter_data['slpm']}, Record: {fighter_data['record']}
    VIOLENCE SCORE: {score}/100
    
    INSTRUCTION: Set 'power' to {score}. Estimate others based on violence (High Stamina/Chin for brawlers).
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "AGGRESSIVE text about their violence/finish rate. Use emojis (🩸, 👊). Max 280 chars.",
        "stat_reply": "Explain WHY they got a violence score of {score}. Max 280 chars.",
        "card_stats": {{ "power": {score}, "grappling": "Est(high if sub/gnp)", "stamina": "Est(high)", "chin": "Est(high for brawlers)", "technique": "Est", "one_liner": "PURE VIOLENCE" }},
        "video_script": "12-second intense script, max 35 words. Focus on destruction. Start with 'WARNING: High Violence...'"
    }}
    """
    try:
        resp = generate_with_retry(client, config.GEMINI_MODELS[0], prompt)
        return parse_json_content(resp.text)
    except Exception: return None

def generate_oracle_content(fighter1, fighter2):
    client = get_gemini_model()
    if not client: return None

    prompt = f"""
    ROLE: The FightIQ Oracle (Future/Fantasy Matchup Predictor).
    MATCHUP: {fighter1['name']} ({fighter1['record']}) vs {fighter2['name']} ({fighter2['record']})
    
    TASK: Simulate this fight & Generate Attribute Stats for BOTH fighters.
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "🔮 THE EXARCHIA HAS SPOKEN. Fantasy Matchup: {fighter1['name']} vs {fighter2['name']}. Who takes it? #FightIQ",
        "stat_reply": "Prediction: [Winner] via [Method]. Reason: [1 sentence analysis].",
        "card_stats": {{
            "fighter1": {{ "power": 75, "grappling": 75, "stamina": 75, "chin": 75, "technique": 75, "one_liner": "3-5 word fighter tag e.g. Pressure Wrestler" }},
            "fighter2": {{ "power": 75, "grappling": 75, "stamina": 75, "chin": 75, "technique": 75, "one_liner": "3-5 word fighter tag" }},
            "one_liner": "FANTASY WAR"
        }},
        "video_script": "12-second script, max 35 words. 'In this corner... The Oracle predicts...' Build tension."
    }}
    """
    try:
        resp = generate_with_retry(client, config.GEMINI_MODELS[0], prompt)
        return parse_json_content(resp.text)
    except Exception: return None

def generate_anomaly_content(fighter1, fighter2, odds_val, stat_note):
    client = get_gemini_model()
    if not client: return None

    # Distinguish between live odds and statistical-only anomaly
    has_live_odds = odds_val not in ("N/A (Statistical)", "N/A", None, "")
    if has_live_odds:
        odds_context = f"LIVE ODDS: {fighter1['name']} is paying {odds_val} (underdog/value)."
        tweet_hook = f"The books have {fighter1['name']} at {odds_val}. The stats say that's wrong."
        stat_hook = f"At {odds_val}, the implied probability is off. Value detected."
    else:
        odds_context = f"No live odds available. This is a pure STATISTICAL anomaly."
        tweet_hook = f"The stats are screaming value on {fighter1['name']}."
        stat_hook = f"Pure stat edge: {stat_note}"

    prompt = f"""
    ROLE: Sharp Sports Bettor / MMA Analyst.
    TASK: Write an engaging value-alert social post for this fighter.
    FIGHTER: {fighter1['name']}
    OPPONENT: {fighter2['name']}
    {odds_context}
    STAT INSIGHT: {stat_note}
    
    Write a viral, punchy tweet (max 240 chars) that:
    - Starts with "🚨 WOLF TICKET:" or similar hook
    - References the actual stat insight naturally (no mention of "N/A")
    - Uses #UFC and one relevant hashtag
    
    OUTPUT ONLY valid JSON:
    {{
        "main_tweet": "<write the main viral tweet here>",
        "stat_reply": "<write a 2nd tweet: the stat breakdown, max 240 chars>",
        "card_stats": {{ "power": 75, "grappling": 75, "stamina": 75, "chin": 80, "technique": 95, "one_liner": "STAT ANOMALY" }},
        "video_script": "12-second script, max 35 words. Build tension: why this fighter is undervalued."
    }}
    """
    try:
        resp = generate_with_retry(client, config.GEMINI_MODELS[0], prompt)
        return parse_json_content(resp.text)
    except Exception: return None

def generate_history_content(fighter_data):
    client = get_gemini_model()
    if not client: return None

    prompt = f"""
    ROLE: MMA Historian.
    TASK: Create a 'Throwback' or 'Hall of Fame' post for veteran: {fighter_data['name']}.
    STATS: Record: {fighter_data['record']}, Wins: {fighter_data['wins']}
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "🕰️ LEGEND STATUS: {fighter_data['name']}. A true veteran of the cage. \\n\\nRemembering their prime today. #UFC #Legends",
        "stat_reply": "Did You Know: {fighter_data['name']} has {fighter_data['wins']} pro wins. A career of violence.",
        "card_stats": {{ "power": "Est(Prime)", "grappling": "Est(Prime)", "stamina": "Est(Prime)", "chin": "Est(Prime/Veteran)", "technique": 95, "one_liner": "UFC VETERAN" }},
        "video_script": "12-second script, max 35 words. 'Years of battles... A legacy written in blood...' Focus on longevity."
    }}
    """
    try:
        resp = generate_with_retry(client, config.GEMINI_MODELS[0], prompt)
        return parse_json_content(resp.text)
    except Exception: return None

# --- SCHEDULING LOGIC ---

def get_dynamic_weights():
    """
    Returns weights for [STANDARD, VIOLENCE, ORACLE, ANOMALY, HISTORY]
    based on the current day of the week.
    """
    day = datetime.today().weekday()  # 0=Mon … 6=Sun

    # Mon / Sat / Sun: reliable single-fighter spotlight (image + 1 stat reply)
    if day in (0, 5, 6):
        label = {0: "MONDAY", 5: "SATURDAY", 6: "SUNDAY"}[day]
        print(f"   📅 Schedule: STANDARD {label} (Strict)")
        return [90, 3, 2, 3, 2]

    if day == 1:
        print("   📅 Schedule: ORACLE TUESDAY (Strict)")
        return [2, 2, 90, 3, 3]
    if day == 2:
        print("   📅 Schedule: VIOLENCE WEDNESDAY (Strict)")
        return [2, 90, 2, 3, 3]
    if day == 3:
        print("   📅 Schedule: THROWBACK THURSDAY (Strict)")
        return [2, 2, 2, 3, 90]
    if day == 4:
        print("   📅 Schedule: WOLF TICKET FRIDAY (Strict)")
        return [2, 2, 2, 90, 3]

    print("   📅 Schedule: STANDARD ROTATION")
    return [30, 15, 15, 25, 15]

# --- MAIN LOOP ---

def main():
    print("--- 🔦 SPOTLIGHT ENGINE ACTIVATED ---")
    
    history = load_history()
    posted_names = [h['name'] for h in history]
    fighters_list, urls = load_db()
    
    # 1. GENERATE CANDIDATE LIST (Trends Priority)
    candidates = []
    if TrendHunter:
        try:
            trending = TrendHunter.get_trending_fighters()
            if trending:
                print(f"   🔥 Trends Found: {len(trending)}")
                candidates.extend([t for t in trending if t in urls])
        except Exception: pass
    
    random.shuffle(fighters_list)
    candidates.extend(fighters_list[:50]) # Add random filler
    
    # 2. SELECT MODE (Dynamic or Manual)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, help="Force a specific mode (STANDARD, VIOLENCE, ORACLE, ANOMALY, HISTORY)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.mode and args.mode.upper() in ["STANDARD", "VIOLENCE", "ORACLE", "ANOMALY", "HISTORY"]:
        mode = args.mode.upper()
        print(f"   🎲 MODE FORCED: {mode}")
    else:
        modes = ["STANDARD", "VIOLENCE", "ORACLE", "ANOMALY", "HISTORY"]
        weights = get_dynamic_weights()
        mode = random.choices(modes, weights=weights, k=1)[0]
        print(f"   🎲 MODE SELECTED: {mode}")
    
    selected_data = None
    ai_content = None
    
    # 3. EXECUTE MODE
    if mode == "ORACLE":
        # ORACLE MODE: Lazy Validation (Pick -> Scrape -> Validate)
        print(f"   🔮 Oracle Mode: Lazy validation (2024+ active fighters)...")
        
        # Build candidate pool (trending + random high-tier names)
        candidate_pool = candidates[:20] if candidates else []
        # Add random high-tier fighters from DB
        shuffled_db = fighters_list.copy()
        random.shuffle(shuffled_db)
        candidate_pool.extend(shuffled_db[:80])  # Total pool of ~100 names
        
        # LAZY VALIDATION: Pick candidates one-by-one, scrape, validate
        valid_fighters = []
        attempts = 0
        max_attempts = 50  # Prevent infinite loop
        
        for candidate_name in candidate_pool:
            if attempts >= max_attempts:
                break
            if candidate_name in posted_names:
                continue
            
            attempts += 1
            print(f"      🔍 Checking {candidate_name}...", end=" ")
            
            # Scrape individual fighter
            fighter_data = scrape_fighter_detailed(urls.get(candidate_name))
            
            if not fighter_data:
                print("❌ No data")
                continue
            
            # Validate criteria
            wins = fighter_data.get('wins', 0)
            last_year = fighter_data.get('last_fight_year')
            
            if wins < 10:
                print(f"❌ Only {wins} wins")
                continue
            
            if not last_year or last_year < 2024:
                print(f"❌ Last fight: {last_year or 'Unknown'}")
                continue
            
            # VALID!
            print(f"✅ Valid ({wins} wins, {last_year})")
            valid_fighters.append((candidate_name, fighter_data))
            
            if len(valid_fighters) >= 10:  # Stop once we have enough
                break
        
        if len(valid_fighters) < 2:
            print(f"   ❌ ORACLE: Only found {len(valid_fighters)} valid fighters. Switching to STANDARD.")
            mode = "STANDARD"
        else:
            # SELECT FIGHTER A
            f1_name, d1 = valid_fighters[0]
            f1_wins = d1.get('wins', 0)
            f1_weight_class = d1.get('weight_class')
            
            print(f"   👤 Fighter A: {f1_name} ({f1_weight_class or 'Unknown Class'})")
            
            # WEIGHT CLASS MATCHING (+/- 1 Division Logic)
            same_weight_class = []
            catchweights = []
            
            WEIGHT_CLASSES = ["Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight",
                              "Middleweight", "Light Heavyweight", "Heavyweight"]
            
            f1_class_clean = f1_weight_class.replace("Women's ", "").strip()
            is_womens = "Women's" in f1_weight_class
            
            # Find index
            try:
                idx = WEIGHT_CLASSES.index(f1_class_clean)
                valid_classes = [f1_class_clean]
                if idx > 0: valid_classes.append(WEIGHT_CLASSES[idx-1])
                if idx < len(WEIGHT_CLASSES)-1: valid_classes.append(WEIGHT_CLASSES[idx+1])
            except Exception:
                valid_classes = [f1_class_clean]

            for name, data in valid_fighters[1:]:
                d_class = data.get('weight_class')
                if not d_class: continue
                
                # Check gender match
                d_is_women = "Women's" in d_class
                if is_womens != d_is_women: continue
                
                d_class_clean = d_class.replace("Women's ", "").strip()
                
                if d_class == f1_weight_class:
                    same_weight_class.append((name, data))
                elif d_class_clean in valid_classes:
                    catchweights.append((name, data))
            
            if same_weight_class:
                # Find balanced opponent in same weight class
                comparable = [(n, d) for n, d in same_weight_class if abs(d.get('wins', 0) - f1_wins) <= config.ORACLE_MAX_WINS_DIFFERENCE]
                if comparable:
                    f2_name, d2 = random.choice(comparable)
                    print(f"   🔮 Oracle Matchup (Balanced {f1_weight_class}): {f1_name} vs {f2_name}")
                else:
                    f2_name, d2 = same_weight_class[0]
                    print(f"   🔮 Oracle Matchup ({f1_weight_class}): {f1_name} vs {f2_name}")
            elif catchweights:
                # Use catchweight
                f2_name, d2 = random.choice(catchweights)
                f2_class = d2.get('weight_class')
                print(f"   🔮 Oracle Matchup (Catchweight {f1_weight_class} vs {f2_class}): {f1_name} vs {f2_name}")
            else:
                # No weight class match, use any valid opponent
                f2_name, d2 = valid_fighters[1]
                print(f"   🔮 Oracle Matchup (Cross-Division): {f1_name} vs {f2_name}")
            
            ai_content = generate_oracle_content(d1, d2)
            
            # Store BOTH fighters for Versus Card
            selected_data = {
                'fighter1': d1,
                'fighter2': d2,
                'name': f1_name
            } 
    
    elif mode == "ANOMALY":
        print(f"   🎲 Hunting for ANOMALIES (Real or Statistical)...")
        found_anomaly = False

        # 1. TRY LIVE ODDS
        if BetistEngine:
            try:
                engine = BetistEngine()
                if not engine.resolve_current_domain():
                    print("   ⚠️ BetistEngine: Domain resolution failed")
                elif not engine.find_ufc_league_id():
                    print("   ⚠️ BetistEngine: UFC League ID not found")
                else:
                    engine.fetch_event_list()
                    for f_name, ev_id in engine.fighter_to_id.items():
                        norm_f_name = " ".join(f_name.split())
                        db_key = None
                        for k in urls.keys():
                            if k.lower() == norm_f_name.lower(): 
                                db_key = k
                                break
                        if not db_key: continue
                        
                        odds_data = engine.fetch_market_detail(ev_id)
                        if odds_data and 'Moneyline' in odds_data:
                            ml = odds_data['Moneyline']
                            my_odd = 0
                            for k, v in ml.items():
                                if norm_f_name.lower() in k.lower(): my_odd = v
                                
                            if my_odd > config.ANOMALY_ODDS_THRESHOLD:
                                d = scrape_fighter_detailed(urls[db_key])
                                if d and d['wins'] > 15:
                                    print(f"   🚨 LIVE ANOMALY: {db_key} is paying {my_odd}!")
                                    ai_content = generate_anomaly_content(d, {"name": "Opponent"}, my_odd, f"Proven veteran ({d['wins']} wins) priced as underdog")
                                    selected_data = d
                                    found_anomaly = True
                                    break
            except Exception as e:
                print(f"   ⚠️ BetistEngine failed: {type(e).__name__}: {e}")
                if '--debug' in sys.argv:
                    traceback.print_exc()
        
        # 2. FALLBACK: STATISTICAL ANOMALY (If Live Odds Fail)
        if not found_anomaly:
            print("   ⚠️ No Live Odds found. Hunting Statistical Anomalies...")
            for _ in range(config.MAX_CANDIDATE_PAIRS):
                n1 = random.choice(candidates)
                n2 = random.choice(candidates)
                if n1 == n2: continue
                d1 = scrape_fighter_detailed(urls[n1])
                d2 = scrape_fighter_detailed(urls[n2])
                if d1 and d2:
                    # Filter out fighters with losing records
                    w1, l1 = d1.get('wins', 0), d1.get('losses', 0)
                    w2, l2 = d2.get('wins', 0), d2.get('losses', 0)
                    if w1 <= l1 or w1 < 3:
                        continue
                    try:
                        acc1 = int(d1.get('str_acc', '0').replace('%',''))
                        acc2 = int(d2.get('str_acc', '0').replace('%',''))
                        if acc1 > acc2 + config.ANOMALY_STAT_DIFF_THRESHOLD:
                             print(f"   📊 Stat Anomaly: {n1} (+{acc1-acc2}% Acc)")
                             ai_content = generate_anomaly_content(d1, d2, "N/A (Statistical)", f"{n1} has +{acc1-acc2}% Striking Accuracy advantage.")
                             selected_data = d1
                             found_anomaly = True
                             break
                    except Exception as e:
                        if '--debug' in sys.argv:
                            print(f"      Debug: Stat parsing error: {e}")
                        continue
        
        # 3. RETRY: Scan more fighters from full DB
        if not found_anomaly:
            print("   🔄 Retry: Scanning full fighter DB for anomalies...")
            shuffled_list = fighters_list.copy()
            random.shuffle(shuffled_list)
            for i in range(0, min(50, len(shuffled_list)), 2):
                if i+1 >= len(shuffled_list): break
                n1, n2 = shuffled_list[i], shuffled_list[i+1]
                d1 = scrape_fighter_detailed(urls.get(n1))
                d2 = scrape_fighter_detailed(urls.get(n2))
                if d1 and d2:
                    # Skip fighters with losing records
                    if d1.get('wins', 0) <= d1.get('losses', 0) or d1.get('wins', 0) < 3:
                        continue
                    try:
                        # Check multiple stats
                        slpm1 = float(d1.get('slpm', 0))
                        slpm2 = float(d2.get('slpm', 0))
                        td1 = float(d1.get('td_avg', 0))
                        td2 = float(d2.get('td_avg', 0))
                        sub1 = float(d1.get('sub_avg', 0))
                        sub2 = float(d2.get('sub_avg', 0))
                        
                        # Priority 1: SLpM anomaly
                        if slpm1 > slpm2 + 2.0:
                            print(f"   📊 SLpM Anomaly: {n1} (+{slpm1-slpm2:.1f} SLpM)")
                            ai_content = generate_anomaly_content(d1, d2, "N/A (Statistical)", f"{n1} lands {slpm1-slpm2:.1f} more strikes per minute")
                            selected_data = d1
                            found_anomaly = True
                            break
                        # Priority 2: TD anomaly
                        elif td1 > td2 + 2.0:
                            print(f"   🤼 TD Anomaly: {n1} ({td1} vs {td2} TD/fight)")
                            ai_content = generate_anomaly_content(d1, d2, "N/A (Statistical)", f"{n1} averages {td1-td2:.1f} more takedowns - wrestling clinic")
                            selected_data = d1
                            found_anomaly = True
                            break
                        # Priority 3: Submission anomaly
                        elif sub1 > sub2 + 0.8:
                            print(f"   🥋 Submission Anomaly: {n1} ({sub1} vs {sub2} subs/fight)")
                            ai_content = generate_anomaly_content(d1, d2, "N/A (Statistical)", f"{n1} is a submission artist with {sub1-sub2:.1f} more subs/fight")
                            selected_data = d1
                            found_anomaly = True
                            break
                    except Exception:
                        continue
        
        if not found_anomaly:
            print("   ❌ ANOMALY mode exhausted all options. Using best available fighter.")
            # As last resort, pick highest odds fighter or most experienced
            for name in candidates[:20]:
                d = scrape_fighter_detailed(urls.get(name))
                if d and d.get('wins', 0) > 15:
                    ai_content = generate_anomaly_content(d, {"name": "The Field"}, "2.5+", f"Veteran with {d['wins']} wins - always a value bet")
                    selected_data = d
                    break

    elif mode == "HISTORY":
        print(f"   🕰️ Searching for Legends ({config.HISTORY_WINS_THRESHOLD}+ Wins)...")
        found_history = False
        
        # Try 1: Primary threshold
        full_list_shuffled = fighters_list.copy()
        random.shuffle(full_list_shuffled)
        
        for name in full_list_shuffled[:config.MAX_FIGHTERS_TO_SCAN]:
            if name in posted_names: continue
            d = scrape_fighter_detailed(urls[name])
            if d and d.get('wins', 0) >= config.HISTORY_WINS_THRESHOLD:
                print(f"   🏛️ Legend Found: {d['name']} ({d['wins']} Wins)")
                ai_content = generate_history_content(d)
                if ai_content:
                    selected_data = d
                    found_history = True
                    break
        
        # Retry 1: Relaxed threshold
        if not found_history:
            print(f"   🔄 Retry: Lowering threshold to {config.HISTORY_WINS_RELAXED}+ wins...")
            for name in full_list_shuffled[:config.MAX_FIGHTERS_TO_SCAN]:
                if name in posted_names: continue
                d = scrape_fighter_detailed(urls[name])
                if d and d.get('wins', 0) >= config.HISTORY_WINS_RELAXED:
                    print(f"   🏛️ Veteran Found: {d['name']} ({d['wins']} Wins)")
                    ai_content = generate_history_content(d)
                    if ai_content:
                        selected_data = d
                        found_history = True
                        break
        
        # Retry 2: Absolute minimum + long career
        if not found_history:
            print(f"   🔄 Final retry: Looking for long careers ({config.HISTORY_MIN_WINS}+ wins)...")
            for name in full_list_shuffled:
                if name in posted_names: continue
                d = scrape_fighter_detailed(urls[name])
                if d and d.get('wins', 0) >= config.HISTORY_MIN_WINS:
                    total_fights = d.get('wins', 0) + d.get('losses', 0)
                    if total_fights >= 25:  # Long career
                        print(f"   🏛️ Career Fighter: {d['name']} ({total_fights} fights)")
                        ai_content = generate_history_content(d)
                        if ai_content:
                            selected_data = d
                            found_history = True
                            break
        
        if not found_history:
            print("   ❌ HISTORY mode: Could not find suitable veteran. Using most experienced available.")
            # Pick fighter with most wins from candidates
            best_wins = 0
            for name in candidates[:50]:
                d = scrape_fighter_detailed(urls.get(name))
                if d and d.get('wins', 0) > best_wins:
                    best_wins = d['wins']
                    selected_data = d
            if selected_data:
                ai_content = generate_history_content(selected_data)
    
    elif mode == "VIOLENCE":
        print(f"   🩸 Hunting for Violence (SLpM > {config.VIOLENCE_SLPM_THRESHOLD})...")
        found_violence = False
        
        # Try 1: Primary threshold from candidates
        for name in candidates:
            if name in posted_names: continue
            d = scrape_fighter_detailed(urls.get(name))
            if d and float(d.get('slpm', 0)) > config.VIOLENCE_SLPM_THRESHOLD:
                print(f"   🩸 Violence Candidate: {d['name']} (SLpM: {d['slpm']})")
                ai_content = generate_violence_content(d)
                if ai_content:
                    selected_data = d
                    found_violence = True
                    break
        
        # Retry 1: Relaxed threshold, broader scan
        if not found_violence:
            print(f"   🔄 Retry: Lowering threshold to {config.VIOLENCE_SLPM_RELAXED}...")
            random.shuffle(fighters_list)
            for name in fighters_list[:config.MAX_FIGHTERS_TO_SCAN]:
                if name in posted_names: continue
                d = scrape_fighter_detailed(urls.get(name))
                if d and float(d.get('slpm', 0)) > config.VIOLENCE_SLPM_RELAXED:
                    print(f"   🩸 Violence Found: {d['name']} (SLpM: {d['slpm']})")
                    ai_content = generate_violence_content(d)
                    if ai_content:
                        selected_data = d
                        found_violence = True
                        break
        
        # Retry 2: Absolute minimum
        if not found_violence:
            print(f"   🔄 Final retry: Minimum threshold {config.VIOLENCE_MIN_SLPM}...")
            for name in fighters_list[:config.MAX_FIGHTERS_TO_SCAN]:
                d = scrape_fighter_detailed(urls.get(name))
                if d and float(d.get('slpm', 0)) > config.VIOLENCE_MIN_SLPM:
                    print(f"   🩸 Brawler Found: {d['name']} (SLpM: {d['slpm']})")
                    ai_content = generate_violence_content(d)
                    if ai_content:
                        selected_data = d
                        found_violence = True
                        break
        
        if not found_violence:
            print("   ❌ VIOLENCE mode: No violent fighters found. Using highest SLpM available.")
            # Pick highest SLpM from all candidates
            best_slpm = 0.0
            for name in candidates[:50]:
                d = scrape_fighter_detailed(urls.get(name))
                if d:
                    slpm = float(d.get('slpm', 0))
                    if slpm > best_slpm:
                        best_slpm = slpm
                        selected_data = d
            if selected_data:
                ai_content = generate_violence_content(selected_data)

    # STANDARD (or Fallback)
    if not selected_data or mode == "STANDARD": 
        print(f"   ✨ Running STANDARD mode (Min {config.STANDARD_MIN_WINS} wins)...")
        for name in candidates:
            if name in posted_names: continue
            d = scrape_fighter_detailed(urls.get(name))
            if d and d.get('wins', 0) >= config.STANDARD_MIN_WINS:
                print(f"   ✨ Standard Candidate: {d['name']}")
                ai_content = generate_standard_content(d)
                if ai_content:
                    selected_data = d
                    break
        
        # Fallback: Lower threshold if no one qualified
        if not selected_data:
            print(f"   🔄 Retry: Lowering minimum wins to {config.STANDARD_MIN_WINS_RELAXED}...")
            for name in candidates[:50]:
                d = scrape_fighter_detailed(urls.get(name))
                if d and d.get('wins', 0) >= config.STANDARD_MIN_WINS_RELAXED:
                    ai_content = generate_standard_content(d)
                    if ai_content:
                        selected_data = d
                        break

    if not selected_data or not ai_content:
        print("   ❌ FATAL: Could not generate content.")
        sys.exit(1)

    # 5. GENERATE ASSETS
    if mode == "ORACLE" and isinstance(selected_data, dict) and 'fighter1' in selected_data:
        # ORACLE MODE: Versus card — fight-week layout (nicknames, stance, UFC official strip)
        d1_raw = selected_data["fighter1"]
        d2_raw = selected_data["fighter2"]
        cs = ai_content.get("card_stats") or {}
        f1_display = prepare_versus_fighter_display(d1_raw, cs.get("fighter1"))
        f2_display = prepare_versus_fighter_display(d2_raw, cs.get("fighter2"))
        official_pair = (scraped_to_official_row(d1_raw), scraped_to_official_row(d2_raw))
        print(f"   Creating Versus Card: {f1_display['name']} vs {f2_display['name']}...")
        VisualEngine.create_versus_card(
            f1_display,
            f2_display,
            cs,
            official_pair,
        )
    else:
        # STANDARD/OTHER MODES: Single Fighter Card
        print(f"   🎨 Creating Visuals for {selected_data['name']}...")
        hunter = VisualEngine.ImageHunter()
        img_path = hunter.get_fighter_image(selected_data['name'])
        
        bg_path = None
        
        VisualEngine.create_stat_card(
            selected_data['name'],
            ai_content['card_stats'],
            ai_content['card_stats']['one_liner'],
            img_path,
            record=selected_data['record'],
            bg_path=bg_path
        )
    
    # 7. SAVE JSON
    # Handle Oracle mode with two fighters
    if mode == "ORACLE" and isinstance(selected_data, dict) and 'fighter1' in selected_data:
        fighter_name = selected_data['fighter1']['name']
        fighter2_name = selected_data['fighter2']['name']
        card_rel_path = versus_basename(fighter_name, fighter2_name)
        poll_opts = [f"Team {fighter_name}", f"Team {fighter2_name}", "Draw", "No Contest"]
    else:
        fighter_name = selected_data['name']
        card_rel_path = card_basename(fighter_name)
        poll_opts = None
    
    card_abs_path = get_output_path(card_rel_path, "visuals")
    if not os.path.exists(card_abs_path):
        print(f"   ❌ FATAL: Visual not created at {card_abs_path}")
        sys.exit(1)

    video_path = None
    if VideoEngine and ai_content.get('video_script'):
        try:
            print("   🎬 Rendering Video...")
            video_path = VideoEngine.create_reel(
                fighter_name,
                card_abs_path,
                ai_content['video_script']
            )
        except Exception as e:
            print(f"   ⚠️ Video rendering failed (continuing without video): {type(e).__name__}: {str(e)[:80]}")
            video_path = None
    
    # Build thread: main tweet + one stat reply (no generic YouTube search spam)
    stat_line = ai_content.get("stat_reply", "").strip()
    thread = [ai_content["main_tweet"]]
    if stat_line:
        prefix = f"📊 {mode}: "
        reply = stat_line if stat_line.startswith("📊") else f"{prefix}{stat_line}"
        if len(reply) > 275:
            reply = reply[:272] + "..."
        thread.append(reply)

    if mode == "ORACLE" and poll_opts:
        thread.append(
            f"🗳️ Who wins? Reply {poll_opts[0]} or {poll_opts[1]} — RT for reach. #FightIQ"
        )

    final_output = {
        "fighter": fighter_name,
        "mode": mode,
        "visual_path": card_abs_path,
        "video_path": video_path,
        "thread": thread,
        "poll_options": None,
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4)

    # NOTE: spotlight_history is now written by the Social Director AFTER a
    # successful post — recording it here burned the fighter even when the
    # tweet never went out.
    print(f"   ✅ DONE! spotlight_ready.json created via {mode} mode.")

if __name__ == "__main__":
    main()