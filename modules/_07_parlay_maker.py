import json
import os
import sys

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.config as config  # Explicit import from core
from core.paths import get_data_path

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = get_data_path("3_results.json")
OUTPUT_FILE = get_data_path("4_parlays.json")

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
        viol = data.get('violence_score', 0)
        angles = data.get('betting_angles', {})
        
        fighters = matchup.split(' vs ')
        f1 = fighters[0] if len(fighters) > 0 else ""
        f2 = fighters[1] if len(fighters) > 1 else ""
        
        def format_pick(text):
            if not text: return text
            t = text
            if 'W1' in t and f1: t = t.replace('W1', f1)
            if 'W2' in t and f2: t = t.replace('W2', f2)
            t = t.replace('Fight to Go the Distance - No', 'Fight Does NOT Go Distance')
            t = t.replace('Fight to Go the Distance: No', 'Fight Does NOT Go Distance')
            return t
        
        # 1. BANKO KUPON (Güven >= config threshold)
        confidence = pred.get('confidence', 0)
        if isinstance(confidence, int) and confidence >= config.PARLAY_SAFE_CONFIDENCE:
            safe = angles.get('safe_pick', {})
            pick_text = safe.get('bet', f"{pred.get('winner', 'Favorite')} ML")
            odds = safe.get('odds', 1.50)
            reason = safe.get('reason', f"High Confidence ({confidence}/10)")
            parlays['safe_slip'].append({
                "match": matchup,
                "pick": format_pick(pick_text),
                "odds": odds,
                "reason": reason[:80] + "..." if len(reason) > 80 else reason
            })

        # 2. ŞİDDET KUPONU (Violence >= config threshold)
        if isinstance(viol, (int, float)) and viol >= config.PARLAY_VIOLENCE_SCORE:
            violence = angles.get('violence_pick', {})
            pick_text = violence.get('bet', "Fight Does NOT Go Distance")
            odds = violence.get('odds', 1.50)
            reason = violence.get('reason', f"Violence Score: {viol}/100. Finish likely.")
            parlays['violence_slip'].append({
                "match": matchup,
                "pick": format_pick(pick_text),
                "odds": odds,
                "reason": reason[:80] + "..." if len(reason) > 80 else reason
            })

        # 3. SÜRPRİZ / VALUE KUPONU
        value = angles.get('value_pick', {})
        if value and value.get('bet'):
            parlays['value_slip'].append({
                "match": matchup,
                "pick": format_pick(value.get('bet')),
                "odds": value.get('odds', 2.50),
                "reason": value.get('reason', "AI Edge")[:80] + "..." if len(value.get('reason', '')) > 80 else value.get('reason', "AI Edge")
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