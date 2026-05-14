import json
import os
import re
import sys

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.config as config
from core.paths import get_data_path
from core.odds_converter import american_to_decimal

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = get_data_path("3_results.json")
MARKETS_FILE = get_data_path("2_data_final.json")
OUTPUT_FILE = get_data_path("4_parlays.json")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _norm_matchup_key(matchup: str):
    if " vs " not in matchup:
        return None
    a, b = matchup.split(" vs ", 1)
    return tuple(sorted([a.strip().lower(), b.strip().lower()]))


def _to_conf_int(v):
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return 0


def _odds_to_decimal(val):
    """Normalize AI / JSON odds to a single decimal price for tickets."""
    if val is None or val == "" or val == 0:
        return None
    if isinstance(val, dict):
        if "decimal" in val and val["decimal"] is not None:
            try:
                return round(float(val["decimal"]), 2)
            except (TypeError, ValueError):
                pass
        if "american" in val and val["american"] is not None:
            try:
                return american_to_decimal(str(val["american"]).replace("+", ""))
            except Exception:
                pass
        return None
    if isinstance(val, str):
        s = val.strip().replace(",", ".")
        if s.startswith(("+", "-")) and re.match(r"^[+-]\d{3,}$", s):
            try:
                return american_to_decimal(s)
            except Exception:
                pass
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    try:
        fv = float(val)
        # Heuristic: AI sometimes outputs American as float (e.g. 250.0 for +250)
        if fv > 50:
            try:
                return american_to_decimal(int(fv))
            except Exception:
                pass
        if 1.01 <= fv <= 100:
            return round(fv, 2)
    except (TypeError, ValueError):
        pass
    return None


def _load_markets_by_matchup():
    out = {}
    path = MARKETS_FILE
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            fights = json.load(f)
    except Exception:
        return out
    for fight in fights:
        fighters = fight.get("fighters") or []
        if len(fighters) != 2:
            continue
        key = tuple(sorted([fighters[0].strip().lower(), fighters[1].strip().lower()]))
        out[key] = fight.get("market_data") or {}
    return out


def _moneyline_map(market_data):
    """Flatten Moneyline / Kazanır / 1x2 markets to fighter_name_lower -> decimal."""
    if not isinstance(market_data, dict):
        return {}
    flat = {}
    for mname, outcomes in market_data.items():
        if not isinstance(outcomes, dict):
            continue
        ml_key = str(mname).lower()
        if ml_key not in ("moneyline", "kazanır", "1x2", "match winner"):
            continue
        for oname, oval in outcomes.items():
            if str(oname).lower() in ("line_movement", "props"):
                continue
            dec = _odds_to_decimal(oval)
            if dec:
                flat[str(oname).strip().lower()] = dec
    return flat


def _decimal_for_fighter(pick_text, f1, f2, ml_flat):
    """Pick best decimal for a pick string using moneyline map."""
    if not pick_text or not ml_flat:
        return None
    pt = pick_text.lower()
    f1l, f2l = f1.strip().lower(), f2.strip().lower()
    # Exact / substring match on book keys
    for name, dec in ml_flat.items():
        if not name:
            continue
        if f1l in pt and (f1l in name or name in f1l):
            return dec
        if f2l in pt and (f2l in name or name in f2l):
            return dec
    for name, dec in ml_flat.items():
        if name and name in pt:
            return dec
    return None


def _enrich_odds(pick_text, matchup, ai_odds, markets_by_matchup):
    dec = _odds_to_decimal(ai_odds)
    if dec and 1.02 < dec < 80:
        return dec
    key = _norm_matchup_key(matchup)
    if not key:
        return dec or None
    md = markets_by_matchup.get(key) or {}
    ml = _moneyline_map(md)
    if " vs " not in matchup:
        return dec
    f1, f2 = matchup.split(" vs ", 1)
    from_ml = _decimal_for_fighter(pick_text, f1, f2, ml)
    if from_ml and 1.02 < from_ml < 80:
        return from_ml
    return dec


def main():
    print("--- 🎫 STEP 7: PARLAY MAKER (COUPON ENGINE) ---")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception:
        print(f"❌ '{INPUT_FILE}' not found or invalid JSON. Run step 5 first.")
        return

    markets_by = _load_markets_by_matchup()

    parlays = {
        "safe_slip": [],
        "violence_slip": [],
        "value_slip": [],
        "metadata": {"total_analyzed": len(results), "markets_enriched": bool(markets_by)},
    }

    print(f"📊 Analyzing {len(results)} fights for betting angles...")

    for item in results:
        matchup = item.get("matchup", "")
        data = item.get("fight_brain_output", {})
        if "error" in data or not data:
            continue

        pred = data.get("prediction", {})
        viol = data.get("violence_score", 0)
        angles = data.get("betting_angles", {})

        fighters = matchup.split(" vs ")
        f1 = fighters[0].strip() if len(fighters) > 0 else ""
        f2 = fighters[1].strip() if len(fighters) > 1 else ""

        def format_pick(text):
            if not text:
                return text
            t = text
            if "W1" in t and f1:
                t = t.replace("W1", f1)
            if "W2" in t and f2:
                t = t.replace("W2", f2)
            t = t.replace("Fight to Go the Distance - No", "Fight Does NOT Go Distance")
            t = t.replace("Fight to Go the Distance: No", "Fight Does NOT Go Distance")
            return t

        confidence = _to_conf_int(pred.get("confidence", 0))
        if confidence >= config.PARLAY_SAFE_CONFIDENCE:
            safe = angles.get("safe_pick", {})
            pick_text = format_pick(safe.get("bet", f"{pred.get('winner', 'Favorite')} ML"))
            odds = _enrich_odds(pick_text, matchup, safe.get("odds"), markets_by)
            if not odds:
                odds = 1.85
            reason = safe.get("reason", f"High Confidence ({confidence}/10)")
            parlays["safe_slip"].append(
                {
                    "match": matchup,
                    "pick": pick_text,
                    "odds": odds,
                    "reason": reason[:80] + "..." if len(reason) > 80 else reason,
                }
            )

        if isinstance(viol, (int, float)) and viol >= config.PARLAY_VIOLENCE_SCORE:
            violence = angles.get("violence_pick", {})
            pick_text = format_pick(violence.get("bet", "Fight Does NOT Go Distance"))
            odds = _enrich_odds(pick_text, matchup, violence.get("odds"), markets_by)
            if not odds:
                odds = 1.75
            reason = violence.get("reason", f"Violence Score: {viol}/100. Finish likely.")
            parlays["violence_slip"].append(
                {
                    "match": matchup,
                    "pick": pick_text,
                    "odds": odds,
                    "reason": reason[:80] + "..." if len(reason) > 80 else reason,
                }
            )

        value = angles.get("value_pick", {})
        if value and value.get("bet"):
            pick_text = format_pick(value.get("bet"))
            odds = _enrich_odds(pick_text, matchup, value.get("odds"), markets_by)
            if not odds:
                odds = 2.4
            reason = value.get("reason", "AI Edge")
            parlays["value_slip"].append(
                {
                    "match": matchup,
                    "pick": pick_text,
                    "odds": odds,
                    "reason": reason[:80] + "..." if len(reason) > 80 else reason,
                }
            )

    print(f"   ✅ Safe Picks: {len(parlays['safe_slip'])}")
    print(f"   ✅ Violence Picks: {len(parlays['violence_slip'])}")
    print(f"   ✅ Value Picks: {len(parlays['value_slip'])}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parlays, f, indent=4)

    print(f"\n📁 Coupons saved to '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
