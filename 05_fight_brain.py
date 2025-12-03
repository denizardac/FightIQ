import json
import google.generativeai as genai
import os
import time
import sys

# ==========================================
# 🔑 API KEY AYARI
# ==========================================
# Buraya API Key'ini yapıştır
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("API Key not found in environment variables!") 

genai.configure(api_key=GEMINI_KEY)

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = "2_data_final.json"
OUTPUT_FILE = "3_results.json"
# Kullanmak istediğimiz en güçlü model
TARGET_MODEL = "models/gemini-2.5-pro" 

def list_available_models():
    """Hata durumunda mevcut modelleri listeler"""
    print("\n⚠️ MODEL BULUNAMADI! Hesabındaki aktif modeller listeleniyor...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   👉 {m.name}")
        print("\n💡 Yukarıdaki isimlerden birini koddaki TARGET_MODEL kısmına yazmalısın.\n")
    except Exception as e:
        print(f"   ❌ Model listesi çekilemedi: {e}")

def clean_json_string(text):
    text = text.replace("```json", "").replace("```", "").strip()
    return text

def analyze_fight(fight_data, model_name):
    f1, f2 = fight_data['fighters']
    
    # Veri Hazırlığı
    stats = fight_data.get('stats', [{}, {}])
    deep_stats = fight_data.get('deep_stats', [{}, {}])
    odds = fight_data.get('betist_odds', "No Odds Available")
    news = fight_data.get('news', [])
    
    news_text = "No recent news."
    if news and len(news) > 0:
        f1_news = [n['title'] for n in news[0][:2]] if len(news[0]) > 0 else []
        f2_news = [n['title'] for n in news[1][:2]] if len(news[1]) > 0 else []
        news_text = f"{f1}: {f1_news} | {f2}: {f2_news}"

    print(f"🧠 FIGHTIQ Processing: {f1} vs {f2}...")
    
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        print(f"   ❌ Model Başlatma Hatası: {e}")
        return {"error": "Model init failed", "tweets": []}
    
    # --- 🔮 THE MASTER PROMPT (GLOBAL EDITION) ---
    prompt = f"""
    ROLE: You are 'FightIQ', an elite MMA Analyst and Sharp Bettor. You analyze stats coldly, ignore the hype, and hunt for market inefficiencies.

    --- 🥊 MATCHUP DATA ---
    RED CORNER: {f1}
    - Basic Stats: {json.dumps(stats[0])}
    - Deep Stats: {json.dumps(deep_stats[0])}
    
    BLUE CORNER: {f2}
    - Basic Stats: {json.dumps(stats[1])}
    - Deep Stats: {json.dumps(deep_stats[1])}
    
    📰 NEWS: {news_text}
    💰 ODDS: {json.dumps(odds)}
    
    --- 🎯 MISSION ---
    Analyze the data and return a JSON with:

    1. **VIOLENCE_SCORE (0-100):** Based on Finish Rates, SLpM, and Defense. >85 means "Don't blink".
    2. **STYLISTIC_MATCHUP:** Technical breakdown (e.g., "High Volume vs. Power Counter-Striker").
    3. **PREDICTION:** Winner, Method, Round, Confidence (1-10).
    4. **VALUE_BET_DETECTOR:** Find the mispriced line. Compare your calculated probability vs. the implied odds. Is the underdog live? Is the "Under 1.5 Rounds" prop too high?
    5. **TWITTER_CONTENT (ENGLISH):** Write 3 viral tweets in a thread format.
       - **Tweet 1 (The Hook):** Violence Score + The Narrative. Use emojis (🔥, 🩸).
       - **Tweet 2 (The Data):** Deep stat analysis proving your point. (e.g. "X has 100% TDD, Y spams takedowns. Bad matchup.")
       - **Tweet 3 (The Sharp Pick):** The Prediction & The Value Bet. Use hashtags: #UFC #MMA #GamblingTwitter #{f1.replace(' ','')} #{f2.replace(' ','')}

    --- OUTPUT FORMAT ---
    Return ONLY a valid JSON object: 
    {{ "violence_score": int, "stylistic_analysis": string, "prediction": {{...}}, "value_bets": {{...}}, "tweets": [string, string, string] }}
    """
    
    try:
        # Temperature 0.3 ile daha tutarlı ve ciddi analizler yaptırıyoruz
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json", "temperature": 0.3})
        return json.loads(clean_json_string(response.text))
    except Exception as e:
        if "404" in str(e):
            list_available_models() # Hata alırsak listeyi göster
            sys.exit(1) # Programı durdur ki kullanıcı düzeltsin
        else:
            print(f"   ⚠️ AI Brain Malfunction: {e}")
            return {"error": str(e), "tweets": []}

def main():
    print(f"--- 🧠 STEP 3: FIGHTIQ NEURAL NETWORK (Model: {TARGET_MODEL}) ---")
    
    if "BURAYA" in GEMINI_KEY:
        print("❌ ERROR: Please insert your Gemini API Key in the script!")
        return

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            fights = json.load(f)
    except:
        print(f"❌ '{INPUT_FILE}' not found.")
        return

    final_results = []
    
    print(f"📂 Loaded {len(fights)} fights. Starting analysis...")
    
    for i, fight in enumerate(fights):
        ai_output = analyze_fight(fight, TARGET_MODEL)
        
        fight_result = {
            "matchup": f"{fight['fighters'][0]} vs {fight['fighters'][1]}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fight_brain_output": ai_output
        }
        
        final_results.append(fight_result)
        
        # API Limit koruması
        print("   ⏳ Thinking... (4s)") 
        time.sleep(4) 

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=4)
        
    print(f"\n✅ MISSION COMPLETE! Results saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()