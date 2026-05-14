import json
import os
import sys
from google import genai
from dotenv import load_dotenv

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

INPUT_FILE = "2_data_final.json"
OUTPUT_FILE = "3_results.json"

# 🔥 MODEL LİSTESİ - EN GÜÇLÜ MODELLER (God Mode)
# Updated from config.py
MODELS_TO_TRY = [
    "gemini-3-pro-preview",                  # PRIMARY: God Mode
    "deep-research-pro-preview-12-2025",     # SECONDARY: Deep analysis
    "gemini-exp-1206",                       # TERTIARY: Experimental
    "gemini-2.0-flash-thinking-exp",         # QUATERNARY: Thinking
    "gemini-1.5-pro-latest"                  # FALLBACK: Always available
]

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================

def get_working_model():
    """Hesabında çalışan en güçlü modeli otomatik bulur"""
    print("   🤖 Selecting best AI model...")
    
    for model_name in MODELS_TO_TRY:
        try:
            # Test the model with new API
            response = client.models.generate_content(
                model=model_name,
                contents="Test"
            )
            
            print(f"   ✅ Connected to: {model_name}")
            return model_name
        except Exception as e:
            print(f"   ⚠️  {model_name} failed: {str(e)[:50]}")
            continue
    
    print("   ❌ ERROR: No working models found!")
    sys.exit(1)

def clean_json(text):
    """Markdown temizleyici"""
    return text.replace("```json", "").replace("```", "").strip()

# Global Model instance (Tekrar tekrar başlatmamak için)
active_model = None

def analyze_matchup(fight_data):
    global active_model
    if not active_model:
        active_model = get_working_model()

    f1, f2 = fight_data['fighters']
    stats = fight_data.get('stats', [{}, {}])
    deep = fight_data.get('deep_stats', [{}, {}])
    odds = fight_data.get('betist_odds', "No Odds")
    
    # Haber başlıklarını metne çevir
    news_list = fight_data.get('news', [])
    news_text = "No News"
    if news_list and len(news_list) > 0:
        n1 = [n['title'] for n in news_list[0][:2]] if len(news_list[0]) > 0 else []
        n2 = [n['title'] for n in news_list[1][:2]] if len(news_list[1]) > 0 else []
        news_text = f"{f1}: {n1} | {f2}: {n2}"

    print(f"🧠 Analyzing: {f1} vs {f2}...")
    
    try:
        # --- MASTER PROMPT (CHECKLIST'E UYGUN) ---
        prompt = f"""
        ROLE: You are 'FightIQ', an elite MMA Analyst and Content Creator.

        MATCHUP: {f1} vs {f2}
        
        [RED CORNER] {f1}: 
        Stats: {json.dumps(stats[0])} | Deep Stats: {json.dumps(deep[0])}
        
        [BLUE CORNER] {f2}: 
        Stats: {json.dumps(stats[1])} | Deep Stats: {json.dumps(deep[1])}
        
        ODDS: {json.dumps(odds)}
        NEWS: {news_text}

        --- MISSION ---
        Generate a JSON output for our Weekly Content Calendar:

        1. **violence_score (0-100):** Based on Finish Rates, SLpM and Aggression.
        
        2. **prediction:** {{"winner": "Name", "method": "KO/Sub/Dec", "confidence": 1-10}}
        
        3. **value_bets:** {{"pick": "Best Bet (e.g. Fighter A by KO)", "reason": "Short value explanation"}}
        
        4. **spotlight_stats (CRITICAL FOR VISUAL CARDS):**
           Rate both fighters 0-100 on these attributes based on their stats (Estimate if needed):
           "{f1}": {{"power": int, "grappling": int, "stamina": int, "chin": int, "technique": int, "one_liner": "Short nickname/style description"}}
           "{f2}": {{"power": int, "grappling": int, "stamina": int, "chin": int, "technique": int, "one_liner": "Short nickname/style description"}}

        5. **content_tweets (FOR WEEKLY SCHEDULE):** Write 3 viral tweets in ENGLISH:
           - "analysis_tweet": Technical breakdown for Tuesday Deep Dive.
           - "violence_tweet": Hype tweet for Thursday Violence Day (Focus on Violence Score).
           - "betting_tweet": Betting focus for Friday Parlay.
        
        6. **spotlight_content (FOR WEDNESDAY):** Write a short, engaging "Fighter Spotlight" paragraph (max 280 chars) about the most interesting fighter in this matchup. Start with "🔦 SPOTLIGHT: [Name]".

        Output ONLY valid JSON.
        """
        
        response = active_model.generate_content(prompt, generation_config={"response_mime_type": "application/json", "temperature": 0.2})
        return json.loads(clean_json(response.text))
        
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
        if i < len(fights) - 1: time.sleep(3)  # 3 saniye (config'ten alınabilir)
    
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