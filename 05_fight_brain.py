import json
import google.generativeai as genai
import os
import time
import sys
from dotenv import load_dotenv

# ==========================================
# ⚙️ KURULUM & GÜVENLİK
# ==========================================
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    # Eğer .env okuyamazsa (Test amaçlı manuel giriş)
    # GEMINI_KEY = "BURAYA_KEY_YAZABILIRSIN" 
    print("❌ CRITICAL: 'GEMINI_API_KEY' not found in .env file!")
    sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

INPUT_FILE = "2_data_final.json"
OUTPUT_FILE = "3_results.json"

# 🔥 MODEL LİSTESİ (Sırayla dener, asla 404 vermez)
MODELS_TO_TRY = [
    "models/gemini-2.5-pro",          # En Yenisi (Varsa efsane)
    "models/gemini-1.5-pro-latest",   # Standart Pro
    "models/gemini-1.5-pro",          # Alternatif isim
    "models/gemini-pro"               # En garantisi (Eski ama çalışır)
]

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================

def get_working_model():
    """Hesabında çalışan en güçlü modeli otomatik bulur"""
    print("   🤖 Selecting best AI model...")
    for model_name in MODELS_TO_TRY:
        try:
            model = genai.GenerativeModel(model_name)
            # Ufak bir test isteği at
            model.generate_content("Test", generation_config={"max_output_tokens": 1})
            print(f"   ✅ Connected to: {model_name}")
            return model
        except Exception:
            continue
    
    print("   ❌ FATAL: No working Gemini models found. Check API Key/Quota.")
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
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f: fights = json.load(f)
    except: 
        print(f"❌ '{INPUT_FILE}' not found. Run Step 4 first.")
        return

    results = []
    print(f"📂 Processing {len(fights)} fights...")
    
    # Model seçimini başta yap
    get_working_model() 
    
    for i, fight in enumerate(fights):
        output = analyze_matchup(fight)
        if output:
            results.append({
                "matchup": f"{fight['fighters'][0]} vs {fight['fighters'][1]}",
                "timestamp": time.strftime("%Y-%m-%d"),
                "fight_brain_output": output
            })
        
        # Rate limit koruması
        if i < len(fights) - 1: time.sleep(2) 

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"\n✅ AI Analysis Complete. Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()