import json
import os
import sys
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path
import core.config as config
from core.prediction_validate import implied_probability, validate_and_unify
from core.market_catalog import summarize_markets_for_prompt
from core.numeric_safe import safe_float
from core.scout_enrich import enrich_scout, build_matchup_context
from core.fighter_rating import compute_matchup_bars, style_one_liner

# UTF-8 Encoding
try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

# ==========================================
# 🧠 STEP 5: FIGHT BRAIN (AI Analysis)
# UPDATED: Using google.genai (new package)
# ==========================================
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    print("❌ CRITICAL: 'GEMINI_API_KEY' not found in .env file!")
    sys.exit(1)

# Initialize client with new API
client = genai.Client(api_key=GEMINI_KEY)

INPUT_FILE = get_data_path("2_data_final.json")
OUTPUT_FILE = get_data_path("3_results.json")

# Model list — loaded from config.py (single source of truth)
MODELS_TO_TRY = config.GEMINI_MODELS

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================

def get_working_model():
    """Find the first model from config.GEMINI_MODELS that responds successfully"""
    print("   🤖 Selecting best AI model...")
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Test"
            )
            print(f"   ✅ Connected to: {model_name}")
            return model_name
        except Exception as e:
            print(f"   ⚠️  {model_name} failed: {str(e)[:60]}")
            time.sleep(2)
            continue
    print("   ❌ ERROR: No working models found!")
    sys.exit(1)

def clean_json(text):
    """Markdown temizleyici"""
    return text.replace("```json", "").replace("```", "").strip()

# Global Model instance (Tekrar tekrar başlatmamak için)
active_model = None

from tenacity import retry, wait_exponential, stop_after_attempt

# ... (Helper)
@retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
def generate_with_retry(model_name, prompt, temperature=None):
    """Generates content with exponential backoff for 429/503 errors."""
    temp = temperature if temperature is not None else getattr(
        config, "AI_TEMPERATURE_PREDICTION", config.AI_TEMPERATURE
    )
    return client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temp,
            top_p=config.AI_TOP_P,
            top_k=config.AI_TOP_K,
        )
    )

def _extract_scout_data(deep_list, stats_list, f1, f2):
    """Extract the most analytically relevant fields for the AI prompt."""
    def safe_ds(dl, idx):
        if isinstance(dl, list) and len(dl) > idx and isinstance(dl[idx], dict):
            return dl[idx]
        return {}
    def safe_st(sl, idx):
        if isinstance(sl, list) and len(sl) > idx and isinstance(sl[idx], dict):
            return sl[idx]
        return {}

    d1, d2 = safe_ds(deep_list, 0), safe_ds(deep_list, 1)
    s1, s2 = safe_st(stats_list, 0), safe_st(stats_list, 1)

    def _first(*vals, default='N/A'):
        for v in vals:
            if v not in (None, '', 'N/A', '--', 0):
                return v
        return default

    def _compute_streaks(last_5):
        """Read last_5_results (most recent first) and produce win/loss streak counts."""
        if not isinstance(last_5, list) or not last_5:
            return 0, 0
        wins, losses = 0, 0
        for r in last_5:
            r_low = str(r).lower()
            if 'win' in r_low and losses == 0:
                wins += 1
                if wins and losses == 0 and wins == len(last_5):
                    continue
            else:
                break
        for r in last_5:
            r_low = str(r).lower()
            if 'loss' in r_low and wins == 0:
                losses += 1
            else:
                break
        return wins, losses

    def _rate(ds, key):
        raw = ds.get(key)
        if raw not in (None, "", "N/A", "--"):
            return safe_float(raw)
        return 0.0

    def scout(name, ds, st):
        last_5 = ds.get('last_5_results', st.get('last_5', []))
        win_streak, loss_streak = _compute_streaks(last_5)
        return {
            "name":            name,
            "record":          f"{ds.get('wins',0)}-{ds.get('losses',0)}-{ds.get('draws',0)}",
            "age":             _first(ds.get('age'), st.get('age')),
            "height":          _first(ds.get('height'), st.get('height')),
            "reach":           _first(ds.get('reach'), st.get('reach')),
            "stance":          _first(ds.get('stance'), st.get('stance')),
            "weight_class":    _first(st.get('weight_class'), ds.get('weight_class')),
            # Striking (only available in stat scout's `stats` dict)
            "SLpM":            _first(st.get('SLpM')),
            "Str_Acc":         _first(st.get('Str_Acc')),
            "SApM":             _first(st.get('SApM')),
            "Str_Def":         _first(st.get('Str_Def')),
            # Grappling
            "TD_Avg":          _first(st.get('TD_Avg')),
            "TD_Acc":          _first(st.get('TD_Acc')),
            "TD_Def":          _first(st.get('TD_Def')),
            "Sub_Avg":         _first(st.get('Sub_Avg')),
            # Finish rates (from deep_dive computed fields)
            "KO_rate":         _rate(ds, "ko_rate"),
            "Sub_rate":        _rate(ds, "sub_rate"),
            "Dec_rate":        _rate(ds, "dec_rate"),
            "first_round_finishes": ds.get('first_round_finishes', 0),
            # Momentum
            "last_5_results":  last_5,
            "win_streak":      win_streak,
            "loss_streak":     loss_streak,
        }

    return scout(f1, d1, s1), scout(f2, d2, s2)


def analyze_matchup(fight_data):
    global active_model
    if not active_model:
        active_model = get_working_model()

    f1, f2 = fight_data['fighters']
    stats    = fight_data.get('stats', [{}, {}])
    deep     = fight_data.get('deep_stats', [{}, {}])
    market   = fight_data.get('market_data', {})

    # Extract line movement from market data
    line_movement_text = "N/A"
    if isinstance(market, dict):
        lm = market.get('line_movement', [])
        if lm and isinstance(lm, list):
            recent = lm[-3:] if len(lm) >= 3 else lm
            line_movement_text = str(recent)

    # News headlines (news_list is shaped [news_for_f1, news_for_f2])
    news_list = fight_data.get('news', [])
    news_text = "None"
    try:
        if isinstance(news_list, list) and news_list:
            n1_src = news_list[0] if len(news_list) > 0 and isinstance(news_list[0], list) else []
            n2_src = news_list[1] if len(news_list) > 1 and isinstance(news_list[1], list) else []
            n1 = [item.get('title', '') for item in n1_src[:2] if isinstance(item, dict)]
            n2 = [item.get('title', '') for item in n2_src[:2] if isinstance(item, dict)]
            if n1 or n2:
                news_text = f"{f1}: {n1} | {f2}: {n2}"
    except Exception as e:
        print(f"   ⚠️ News parsing skipped: {type(e).__name__}: {str(e)[:60]}")

    scout1, scout2 = _extract_scout_data(deep, stats, f1, f2)
    n1 = news_list[0] if isinstance(news_list, list) and len(news_list) > 0 and isinstance(news_list[0], list) else []
    n2 = news_list[1] if isinstance(news_list, list) and len(news_list) > 1 and isinstance(news_list[1], list) else []
    scout1 = enrich_scout(scout1, n1)
    scout2 = enrich_scout(scout2, n2)
    matchup_ctx = build_matchup_context(scout1, scout2, n1, n2)
    print(f"🧠 Analyzing: {f1} vs {f2}...")

    try:
        odds_json = json.dumps(market) if isinstance(market, dict) else str(market)
        market_summary = summarize_markets_for_prompt(market, f1, f2)

        prompt = f"""You are FightIQ — a professional MMA betting analyst (sharp, data-driven).
Analyze this UFC matchup. Pick the BEST AVAILABLE BET TYPE from the market board (not always ML).

CRITICAL RULES:
1. ONE winner in prediction.winner — all winner-side bets must match this name.
2. safe_pick = lowest-risk bet (often favorite ML, or Fight Goes Distance if grinders).
3. value_pick = highest-edge bet on the winner OR fight total (method, rounds, ML) — use real odds from the board.
4. violence_pick = Over/Under rounds OR distance market aligned with violence_score (finishes vs decision).
5. Each pick MUST include bet_type: ml | ko | sub | dec | over | under | distance_yes | distance_no
6. If a method/rounds line offers better value than ML, USE IT for value_pick and say so in betting_tweet.
7. Confidence 1–10: 8+ only when stats + market align. Cite numbers (SLpM, TD%, ranking_proxy, injury flags).
8. Do NOT invent odds — copy from AVAILABLE MARKETS or use 0.0.

═══════════════════════════════════════════════════
MATCHUP: {f1.upper()} vs {f2.upper()}
═══════════════════════════════════════════════════

[FIGHTER 1 — {f1}]
{json.dumps(scout1, indent=2)}

[FIGHTER 2 — {f2}]
{json.dumps(scout2, indent=2)}

[MATCHUP CONTEXT — derived]
{json.dumps(matchup_ctx, indent=2)}

[AVAILABLE MARKETS — pick from these lines]
{market_summary}
Line Movement: {line_movement_text}
Full JSON: {odds_json}

[RECENT NEWS]
{news_text}

═══════════════════════════════════════════════════
ANALYTICAL INSTRUCTIONS
═══════════════════════════════════════════════════

Use ALL provided data. Key factors to consider:
- Reach advantage and how it affects striking distance
- Stance matchup (orthodox vs southpaw = southpaw has advantage)
- Age and career trajectory (decline after ~33 for most fighters)
- Last 5 results for momentum and psychological state
- Line movement direction (sharp money vs public betting)
- KO/Sub rates, finish_rate_pct, ranking_proxy (experience/quality proxy)
- injury_news_flag in scout data — downgrade confidence if True for your pick
- Reach / stance / momentum from MATCHUP CONTEXT
- Opponent quality via win_rate_pct and total_fights

═══════════════════════════════════════════════════
OUTPUT (strict JSON, no markdown)
═══════════════════════════════════════════════════

Return ONLY this JSON object:

{{
  "violence_score": <0-100 integer based on SLpM, KO rates, chin durability>,

  "prediction": {{
    "winner": "<fighter name>",
    "method": "<KO | TKO | Sub | Dec | Split Dec>",
    "confidence": <1-10>,
    "key_factor": "<1 sentence: the single most decisive factor>"
  }},

  "betting_angles": {{
    "safe_pick": {{
      "bet": "<exact market label e.g. 'Fighter ML' or 'Under 2.5 Rounds' or 'Fight Goes Distance'>",
      "bet_type": "<ml|ko|sub|dec|over|under|distance_yes|distance_no>",
      "odds": <decimal from board or 0.0>,
      "reason": "<2 sentences with stats>"
    }},
    "violence_pick": {{
      "bet": "<Over 2.5 / Under 2.5 / Fight Does NOT Go Distance / etc. from board>",
      "bet_type": "<over|under|distance_yes|distance_no|ko>",
      "odds": <decimal or 0.0>,
      "reason": "<2 sentences>"
    }},
    "value_pick": {{
      "bet": "<BEST EDGE bet on winner or fight total — method prop preferred when finish likely>",
      "bet_type": "<ml|ko|sub|dec|over|under|...>",
      "odds": <decimal or 0.0>,
      "reason": "<why this line beats ML value>"
    }}
  }},

  "content_tweets": {{
    "analysis_tweet": "<Max 260 chars. Stat-led preview + winner. End #UFC #MMA>",
    "violence_tweet": "<Max 260 chars. Violence score + finish angle. End #UFC>",
    "betting_tweet": "<Max 260 chars. State EXACT bet from value_pick (not always ML). Include odds. End #UFC #Betting>"
  }},

  "spotlight_content": "<Max 275 chars. Wednesday Fighter Spotlight. Start with: 🔦 SPOTLIGHT: [Name]. Hook with the most jaw-dropping stat or career moment. English only.>"
}}"""

        response = generate_with_retry(active_model, prompt)
        output = json.loads(clean_json(response.text))
        output = validate_and_unify(
            output, f1, f2,
            market if isinstance(market, dict) else {},
            scout1, scout2,
        )
        # Deterministic bars for visuals (no AI 96 vs 49)
        d0 = deep[0] if isinstance(deep, list) and len(deep) > 0 else {}
        d1 = deep[1] if isinstance(deep, list) and len(deep) > 1 else {}
        bars = compute_matchup_bars(scout1, scout2, d0, d1)
        winner = output.get("prediction", {}).get("winner", f1)
        output["computed_ratings"] = bars
        output["spotlight_stats"] = {
            f1: {
                **bars["fighter1"],
                "one_liner": style_one_liner(scout1, d0),
            },
            f2: {
                **bars["fighter2"],
                "one_liner": style_one_liner(scout2, d1),
            },
        }
        return output
        
    except Exception as e:
        print(f"   ⚠️ AI Analysis Error: {e}")
        return None

def main():
    print(f"--- 🧠 STEP 5: FIGHT BRAIN (ROBUST V2) ---")
    
    # Robust file load
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: '{INPUT_FILE}' not found. Run Step 4 first.")
        return
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f: 
            fights = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON in {INPUT_FILE}: {e}")
        return

    results = []
    failed_fights = []
    print(f"📂 Processing {len(fights)} fights...")
    
    # Model seçimini başta yap
    get_working_model() 
    
    for i, fight in enumerate(fights):
        matchup_name = f"{fight['fighters'][0]} vs {fight['fighters'][1]}"
        output = analyze_matchup(fight)
        
        if output:
            # Validate essential fields
            required_fields = ['prediction', 'violence_score']
            if all(field in output for field in required_fields):
                results.append({
                    "matchup": matchup_name,
                    "timestamp": time.strftime("%Y-%m-%d"),
                    "fight_brain_output": output
                })
                print(f"   ✅ Analysis complete")
            else:
                print(f"   ⚠️ WARNING: Incomplete AI output for {matchup_name}, retrying...")
                # Retry once
                output_retry = analyze_matchup(fight)
                if output_retry and all(field in output_retry for field in required_fields):
                    results.append({
                        "matchup": matchup_name,
                        "timestamp": time.strftime("%Y-%m-%d"),
                        "fight_brain_output": output_retry
                    })
                    print(f"   ✅ Retry successful")
                else:
                    failed_fights.append(matchup_name)
                    print(f"   ❌ Failed after retry")
        else:
            failed_fights.append(matchup_name)
            print(f"   ❌ AI analysis failed for {matchup_name}")
        
        # Rate limit koruması (Deep models için daha uzun bekleme)
        if i < len(fights) - 1: time.sleep(config.AI_REQUEST_DELAY_SECONDS)
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"   ✅ Successful: {len(results)}/{len(fights)}")
    if failed_fights:
        print(f"   ❌ Failed: {len(failed_fights)}")
        print(f"   Failed fights: {', '.join(failed_fights)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"\n✅ AI Analysis Complete. Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()