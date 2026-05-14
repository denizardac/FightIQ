import json
import random
import os
import requests
import sys
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai
from dotenv import load_dotenv
import urllib.parse
import time
import importlib.util
import traceback

# Import config
try:
    import config
except ImportError:
    print("⚠️ config.py not found, using defaults")
    class config:
        VIOLENCE_SLPM_THRESHOLD = 4.0
        VIOLENCE_SLPM_RELAXED = 3.0
        VIOLENCE_MIN_SLPM = 2.5
        HISTORY_WINS_THRESHOLD = 20
        HISTORY_WINS_RELAXED = 15
        HISTORY_MIN_WINS = 10
        STANDARD_MIN_WINS = 10
        ANOMALY_ODDS_THRESHOLD = 2.20
        ANOMALY_STAT_DIFF_THRESHOLD = 15
        MAX_FIGHTERS_TO_SCAN = 100
        MAX_CANDIDATE_PAIRS = 10
        ORACLE_MAX_WINS_DIFFERENCE = 5
        FUZZY_MATCH_CUTOFF = 0.8

# --- IMPORT MODULES ---
try:
    spec_t = importlib.util.spec_from_file_location("TrendHunter", "11_trend_hunter.py")
    TrendHunter = importlib.util.module_from_spec(spec_t)
    spec_t.loader.exec_module(TrendHunter)
except Exception:
    TrendHunter = None

try:
    spec_o = importlib.util.spec_from_file_location("OddsHunter", "03_odds_hunter.py")
    OddsHunterModule = importlib.util.module_from_spec(spec_o)
    spec_o.loader.exec_module(OddsHunterModule)
    BetistEngine = OddsHunterModule.BetistEngine
except Exception as e:
    print(f"⚠️ OddsHunter not available: {type(e).__name__}")
    BetistEngine = None

try:
    spec = importlib.util.spec_from_file_location("VisualEngine", "06_visual_engine.py")
    VisualEngine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(VisualEngine)
except Exception as e:
    print(f"❌ Error: 06_visual_engine.py not available: {type(e).__name__}")
    sys.exit(1)

try:
    spec_v = importlib.util.spec_from_file_location("VideoEngine", "10_video_engine.py")
    VideoEngine = importlib.util.module_from_spec(spec_v)
    spec_v.loader.exec_module(VideoEngine)
except Exception as e:
    print(f"⚠️ Warning: VideoEngine not available ({type(e).__name__}). Video generation skipped.")
    VideoEngine = None

# --- CONFIG ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

DB_FILE = "fighters_db.json"
HISTORY_FILE = "spotlight_history.json"
OUTPUT_FILE = "spotlight_ready.json"

# --- HELPERS ---

def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f: 
            data = json.load(f)
            ninety_days_ago = datetime.now() - timedelta(days=90)
            return [x for x in data if datetime.strptime(x['date'], "%Y-%m-%d") > ninety_days_ago]
    except: return []

def save_history(history, name):
    history.append({"name": name, "date": datetime.now().strftime("%Y-%m-%d")})
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: db = json.load(f)
        if "data" in db: return list(db["data"].keys()), db["data"]
        else: return list(db.keys()), db
    except: return [], {}

def get_gemini_model():
    models = ["models/gemini-2.5-pro", "models/gemini-1.5-pro-latest", "models/gemini-pro"]
    for m in models:
        try: return genai.GenerativeModel(m)
        except: continue
    return None

def scrape_fighter_detailed(url):
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
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
        data['td_avg'] = "0.00"
        data['sub_avg'] = "0.0"
        
        for item in soup.find_all('li', class_='b-list__box-list-item_type_block'):
            text = " ".join(item.text.split())
            if "SLpM:" in text: data['slpm'] = text.split("SLpM:")[1].strip()
            if "Str. Acc.:" in text: data['str_acc'] = text.split("Str. Acc.:")[1].strip()
            if "TD Avg.:" in text: data['td_avg'] = text.split("TD Avg.:")[1].strip()
            if "Sub. Avg.:" in text: data['sub_avg'] = text.split("Sub. Avg.:")[1].strip()

        return data
    except: return None

# --- GENERATORS ---

def generate_standard_content(fighter_data):
    model = get_gemini_model()
    if not model: return None
    
    prompt = f"""
    ROLE: MMA Content Creator.
    TASK: Create content for UFC fighter: {fighter_data['name']}
    STATS: Record: {fighter_data['record']}, SLpM: {fighter_data['slpm']}, Sub Avg: {fighter_data['sub_avg']}
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "High-energy text. Focus on nickname/skill. End with question. Max 280 chars.",
        "stat_reply": "A 'Did You Know' tweet about their style. Max 280 chars.",
        "card_stats": {{ "power": 80, "grappling": 75, "stamina": 85, "technique": 80, "one_liner": "3-5 word cool description" }},
        "video_script": "30s hype script. No 'AI' mentions. Start with 'This is...'."
    }}
    """
    try:
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"Error GenStandard: {e}")
        return None

def generate_violence_content(fighter_data):
    # Calculate Violence Score
    try:
        slpm = float(fighter_data.get('slpm', 0))
        wins = fighter_data.get('wins', 0)
        score = min(99, int((slpm * 10) + (wins * 0.5)))
    except: score = 75

    model = get_gemini_model()
    if not model: return None

    prompt = f"""
    ROLE: The 'Just Bleed' God.
    TASK: Create VIOLENCE RATING content for: {fighter_data['name']}
    STATS: SLpM: {fighter_data['slpm']}, Record: {fighter_data['record']}
    VIOLENCE SCORE: {score}/100
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "AGGRESSIVE text about their violence/finish rate. Use emojis (🩸, 👊). Max 280 chars.",
        "stat_reply": "Explain WHY they got a violence score of {score}. Max 280 chars.",
        "card_stats": {{ "power": {score}, "grappling": 70, "stamina": 85, "technique": 80, "one_liner": "PURE VIOLENCE" }},
        "video_script": "30s intense script focusing ONLY on damage/action. Start with 'WARNING: High Violence...'."
    }}
    """
    try:
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except: return None

def generate_oracle_content(fighter1, fighter2):
    model = get_gemini_model()
    if not model: return None

    prompt = f"""
    ROLE: The FightIQ Oracle (Future/Fantasy Matchup Predictor).
    MATCHUP: {fighter1['name']} ({fighter1['record']}) vs {fighter2['name']} ({fighter2['record']})
    
    TASK: Simulate this fight. Pick a winner based on styles.
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "🔮 THE EXARCHIA HAS SPOKEN. Fantasy Matchup: {fighter1['name']} vs {fighter2['name']}. Who takes it? #FightIQ",
        "stat_reply": "Prediction: [Winner] via [Method]. Reason: [1 sentence analysis].",
        "card_stats": {{ "power": 88, "grappling": 88, "stamina": 88, "technique": 88, "one_liner": "FANTASY WAR" }},
        "video_script": "30s script. 'In this corner... and in this corner... The Oracle predicts...' Build tension."
    }}
    """
    try:
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except: return None

def generate_anomaly_content(fighter1, fighter2, odds_val, stat_note):
    model = get_gemini_model()
    if not model: return None

    prompt = f"""
    ROLE: Sharp Sports Bettor / Analyst.
    TASK: Identify a Betting Value/Anomaly based on LIVE ODDS.
    MATCHUP: {fighter1['name']} vs {fighter2['name']}
    LIVE ODDS: {fighter1['name']} is paying {odds_val} (Underdog/Value).
    STAT INSIGHT: {stat_note}
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "🚨 WOLF TICKET ALERT 🚨\\n\\nThe books are giving us {odds_val} on {fighter1['name']}?! The stats tell a different story. 🐺💰 #UFC #Betting",
        "stat_reply": "Deep Dive: {stat_note}. At {odds_val}, the implied probability is wrong. Value detected.",
        "card_stats": {{ "power": 75, "grappling": 75, "stamina": 75, "technique": 95, "one_liner": "ODDS: {odds_val}" }},
        "video_script": "30s analysis script. 'They set the line at {odds_val}... Big mistake. Here is why {fighter1['name']} upsets the odds...'"
    }}
    """
    try:
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except: return None

def generate_history_content(fighter_data):
    model = get_gemini_model()
    if not model: return None

    prompt = f"""
    ROLE: MMA Historian.
    TASK: Create a 'Throwback' or 'Hall of Fame' post for veteran: {fighter_data['name']}.
    STATS: Record: {fighter_data['record']}, Wins: {fighter_data['wins']}
    
    OUTPUT JSON ONLY:
    {{
        "main_tweet": "🕰️ LEGEND STATUS: {fighter_data['name']}. A true veteran of the cage. \\n\\nRemembering their prime today. #UFC #Legends",
        "stat_reply": "Did You Know: {fighter_data['name']} has {fighter_data['wins']} pro wins. A career of violence.",
        "card_stats": {{ "power": 90, "grappling": 85, "stamina": 80, "technique": 95, "one_liner": "UFC VETERAN" }},
        "video_script": "30s nostalgic script. 'Years of battles... A legacy written in blood...' Focus on longevity."
    }}
    """
    try:
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text.replace("```json", "").replace("```", "").strip())
    except: return None

# --- SCHEDULING LOGIC ---

def get_dynamic_weights():
    """
    Returns weights for [STANDARD, VIOLENCE, ORACLE, ANOMALY, HISTORY]
    based on the current day of the week to align with idle_schedule.md.
    """
    day = datetime.today().weekday() # 0=Mon, 1=Tue, ..., 6=Sun
    
    # Default: Balanced but Standard heavy
    weights = [30, 15, 15, 25, 15]
    
    # STRICTER ENFORCEMENT (90% Priority)
    if day == 1: # TUESDAY (Engagement/polls) -> Oracle
        print("   📅 Schedule: ORACLE TUESDAY (Strict)")
        weights = [2, 2, 90, 3, 3]
    elif day == 2: # WEDNESDAY (Violence)
        print("   📅 Schedule: VIOLENCE WEDNESDAY (Strict)")
        weights = [2, 90, 2, 3, 3]
    elif day == 3: # THURSDAY (Throwback) -> History
        print("   📅 Schedule: THROWBACK THURSDAY (Strict)")
        weights = [2, 2, 2, 3, 90]
    elif day == 4: # FRIDAY (Betting/Wolf Tickets) -> Anomaly
        print("   📅 Schedule: WOLF TICKET FRIDAY (Strict)")
        weights = [2, 2, 2, 90, 3]
    else:
        print("   📅 Schedule: STANDARD ROTATION")
        
    return weights

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
        except: pass
    
    random.shuffle(fighters_list)
    candidates.extend(fighters_list[:50]) # Add random filler
    
    # 2. SELECT MODE (Dynamic Scheduling)
    modes = ["STANDARD", "VIOLENCE", "ORACLE", "ANOMALY", "HISTORY"]
    weights = get_dynamic_weights()
    mode = random.choices(modes, weights=weights, k=1)[0]
    print(f"   🎲 MODE SELECTED: {mode}")
    
    selected_data = None
    ai_content = None
    
    # 3. EXECUTE MODE
    if mode == "ORACLE":
        # Improved matchup selection
        f1_name = candidates[0] if candidates else random.choice(fighters_list)
        
        # Try to find comparable opponent
        d1 = scrape_fighter_detailed(urls.get(f1_name))
        f2_name = None
        comparable_opponents = []
        
        if d1:
            f1_wins = d1.get('wins', 0)
            # Search for fighters with similar win count
            for candidate in candidates[1:20]:
                if candidate == f1_name or candidate in posted_names:
                    continue
                d_temp = scrape_fighter_detailed(urls.get(candidate))
                if d_temp:
                    wins_diff = abs(d_temp.get('wins', 0) - f1_wins)
                    if wins_diff <= config.ORACLE_MAX_WINS_DIFFERENCE:
                        comparable_opponents.append(candidate)
            
            if comparable_opponents:
                f2_name = random.choice(comparable_opponents)
                print(f"   🔮 Oracle Matchup (Balanced): {f1_name} vs {f2_name}")
            else:
                # Fallback to any candidate
                f2_name = candidates[1] if len(candidates) > 1 else random.choice(fighters_list)
                print(f"   🔮 Oracle Matchup (Fantasy): {f1_name} vs {f2_name}")
        else:
            f2_name = candidates[1] if len(candidates) > 1 else random.choice(fighters_list)
            print(f"   🔮 Oracle Matchup: {f1_name} vs {f2_name}")
        
        d2 = scrape_fighter_detailed(urls.get(f2_name))
        if d1 and d2:
            ai_content = generate_oracle_content(d1, d2)
            selected_data = d1
        elif d1:
            # If d2 failed, retry with another fighter
            print("   ⚠️ Opponent scraping failed, retrying...")
            f2_name = random.choice(fighters_list)
            d2 = scrape_fighter_detailed(urls.get(f2_name))
            if d2:
                ai_content = generate_oracle_content(d1, d2)
                selected_data = d1 
    
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
                        
                        odds_data = engine.fetch_market_details(ev_id, "F1", "F2")
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
                    except:
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
            print("   🔄 Retry: Lowering minimum wins to 5...")
            for name in candidates[:50]:
                d = scrape_fighter_detailed(urls.get(name))
                if d and d.get('wins', 0) >= 5:
                    ai_content = generate_standard_content(d)
                    if ai_content:
                        selected_data = d
                        break

    if not selected_data or not ai_content:
        print("   ❌ FATAL: Could not generate content.")
        return

    # 5. GENERATE ASSETS
    print(f"   🎨 Creating Visuals for {selected_data['name']}...")
    hunter = VisualEngine.ImageHunter()
    img_path = hunter.get_fighter_image(selected_data['name'])
    
    # Custom Background Logic (Placeholder for now)
    bg_path = None 
    
    VisualEngine.create_stat_card(
        selected_data['name'],
        ai_content['card_stats'],
        ai_content['card_stats']['one_liner'],
        img_path,
        record=selected_data['record'],
        bg_path=bg_path
    )
    
    video_path = None
    if VideoEngine and ai_content.get('video_script'):
        print(f"   🎥 Rendering Video...")
        card_path = f"visuals/Card_{selected_data['name'].replace(' ','_')}.png"
        video_path = VideoEngine.create_reel(
            selected_data['name'],
            card_path,
            ai_content['video_script']
        )

    # 6. SAVE OUTPUT
    yt_link = f"https://www.youtube.com/results?search_query={urllib.parse.quote(selected_data['name'] + ' ufc highlights')}"
    
    final_output = {
        "fighter": selected_data['name'],
        "visual_path": f"visuals/Card_{selected_data['name'].replace(' ','_')}.png",
        "video_path": video_path,
        "thread": [
            ai_content['main_tweet'],
            f"📊 {mode} STATS: {ai_content['stat_reply']}",
            f"📺 MORE ACTION:\n{yt_link}"
        ],
        "poll_options": ["Team " + selected_data['name'], "The Opponent", "Draw/DQ", "Double KO"] if mode == "ORACLE" else None
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4)
        
    save_history(history, selected_data['name'])
    print(f"   ✅ DONE! spotlight_ready.json created via {mode} mode.")

if __name__ == "__main__":
    main()