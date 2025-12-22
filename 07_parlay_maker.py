import json
import os
import sys

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = "3_results.json"
OUTPUT_FILE = "4_parlays.json"

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

def main():
    print("--- 🎫 STEP 7: PARLAY MAKER (COUPON ENGINE) ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except:
        print(f"❌ '{INPUT_FILE}' not found. Run step 5 first.")
        return

    # Kupon Sepetleri
    parlays = {
        "safe_slip": [],      # Banko
        "violence_slip": [],  # Şiddet / Erken Bitme
        "value_slip": [],     # Sürpriz / Yüksek Oran
        "metadata": {
            "total_analyzed": len(results)
        }
    }
    
    print(f"📊 Analyzing {len(results)} fights for betting angles...")
    
    for item in results:
        matchup = item['matchup']
        data = item.get('fight_brain_output', {})
        
        # Hata varsa atla
        if "error" in data or not data: continue
        
        # Verileri Çek
        pred = data.get('prediction', {})
        val = data.get('value_bets', {})
        viol = data.get('violence_score', 0)
        
        # 1. BANKO KUPON (Güven >= 8)
        confidence = pred.get('confidence', 0)
        if isinstance(confidence, int) and confidence >= 8:
            parlays['safe_slip'].append({
                "match": matchup,
                "pick": f"{pred.get('winner')} ML", # ML = Moneyline (Kazanır)
                "reason": f"High Confidence ({confidence}/10). {val.get('reasoning', '')[:50]}..."
            })

        # 2. ŞİDDET KUPONU (Violence >= 80)
        # Bu maçlar genelde "Jüriye Gitmez" (FDGTD) veya "Under" biter.
        if isinstance(viol, int) and viol >= 80:
            parlays['violence_slip'].append({
                "match": matchup,
                "pick": "Fight Does NOT Go Distance / Under 2.5",
                "reason": f"Violence Score: {viol}/100. Finish likely."
            })

        # 3. SÜRPRİZ / VALUE KUPONU
        # AI "risky_bet" önerdiyse veya "Value" kelimesi geçiyorsa
        safe_bet = val.get('safe_bet', '')
        risky_bet = val.get('risky_bet', '')
        
        # Eğer AI özellikle bir underdog veya prop önerdiyse
        if risky_bet and risky_bet != "N/A":
            parlays['value_slip'].append({
                "match": matchup,
                "pick": risky_bet,
                "reason": "AI Detected Market Inefficiency"
            })

    # İstatistik
    print(f"   ✅ Safe Picks: {len(parlays['safe_slip'])}")
    print(f"   ✅ Violence Picks: {len(parlays['violence_slip'])}")
    print(f"   ✅ Value Picks: {len(parlays['value_slip'])}")

    # Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parlays, f, indent=4)
        
    print(f"\n📁 Coupons saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()