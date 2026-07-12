import json
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.config as config
from core.paths import get_data_path
from core.pipeline_meta import stamp_stage
from core.odds_converter import american_to_decimal
from core.odds_resolve import resolve_pick_odds
from core.parlay_logic import (
    pick_matches_winner,
    leg_odds_ok,
    combined_odds,
    edge_score,
    trim_slip,
)

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
    """Returns (markets_by_key, source_by_key) so legs carry an odds_source stamp."""
    out = {}
    sources = {}
    path = MARKETS_FILE
    if not os.path.exists(path):
        return out, sources
    try:
        with open(path, "r", encoding="utf-8") as f:
            fights = json.load(f)
    except Exception:
        return out, sources
    for fight in fights:
        fighters = fight.get("fighters") or []
        if len(fighters) != 2:
            continue
        key = tuple(sorted([fighters[0].strip().lower(), fighters[1].strip().lower()]))
        out[key] = fight.get("market_data") or {}
        sources[key] = fight.get("odds_source_primary") or "unknown"
    return out, sources


def _moneyline_map(market_data):
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
    if not pick_text or not ml_flat:
        return None
    pt = pick_text.lower()
    f1l, f2l = f1.strip().lower(), f2.strip().lower()
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


def _enrich_odds(pick_text, matchup, ai_odds, markets_by_matchup, bet_type="ml", winner="", method="Dec"):
    key = _norm_matchup_key(matchup)
    if not key or " vs " not in matchup:
        return _odds_to_decimal(ai_odds)
    f1, f2 = matchup.split(" vs ", 1)
    md = markets_by_matchup.get(key) or {}
    dec, _, ok = resolve_pick_odds(
        pick_text, bet_type, md, f1.strip(), f2.strip(), winner, method, ai_odds
    )
    return dec if ok else None


def _format_pick(text, f1, f2):
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


def _winner_ml_pick(winner, f1, f2, markets_by, matchup, method="Dec"):
    pick = f"{winner} ML"
    odds = _enrich_odds(pick, matchup, None, markets_by, "ml", winner, method)
    return pick, odds


def _build_safe_candidates(rows, markets_by):
    out = []
    for row in rows:
        matchup = row["matchup"]
        data = row["data"]
        pred = row["pred"]
        angles = row["angles"]
        f1, f2 = row["f1"], row["f2"]
        conf = row["confidence"]

        winner = pred.get("winner", "")
        method = pred.get("method", "Dec")
        safe = angles.get("safe_pick", {})
        pick_text = _format_pick(safe.get("bet", f"{winner} ML"), f1, f2)
        if not pick_matches_winner(pick_text, winner, f1, f2):
            pick_text, _ = _winner_ml_pick(winner, f1, f2, markets_by, matchup, method)

        odds = _enrich_odds(
            pick_text, matchup, safe.get("odds"), markets_by,
            safe.get("bet_type", "ml"), winner, method,
        )
        if not odds or odds < 1.1:
            continue
        reason = safe.get("reason", f"Confidence {conf}/10")
        out.append({
            "match": matchup,
            "pick": pick_text,
            "odds": odds,
            "reason": reason[:80] + "..." if len(reason) > 80 else reason,
            "_conf": conf,
        })
    out.sort(key=lambda x: (-x["_conf"], x["odds"]))
    for leg in out:
        leg.pop("_conf", None)
    return trim_slip(out)


def _build_violence_candidates(rows, markets_by):
    out = []
    for row in rows:
        if row["viol"] < config.PARLAY_VIOLENCE_SCORE_FALLBACK:
            continue
        matchup = row["matchup"]
        pred = row["pred"]
        winner = pred.get("winner", "")
        method = pred.get("method", "Dec")
        violence = row["angles"].get("violence_pick", {})
        if violence.get("odds_available") is False and not violence.get("odds"):
            continue
        pick_text = _format_pick(violence.get("bet", "Fight Does NOT Go Distance"), row["f1"], row["f2"])
        odds = _enrich_odds(
            pick_text, matchup, violence.get("odds"), markets_by,
            violence.get("bet_type", "distance_no"), winner, method,
        )
        if not odds or odds < 1.1:
            continue
        reason = violence.get("reason", f"Violence {row['viol']}/100")
        out.append({
            "match": matchup,
            "pick": pick_text,
            "odds": odds,
            "reason": reason[:80] + "..." if len(reason) > 80 else reason,
            "_viol": row["viol"],
        })
    out.sort(key=lambda x: -x["_viol"])
    for leg in out:
        leg.pop("_viol", None)
    return trim_slip(out)


def _build_value_candidates(rows, markets_by):
    """Model edge slip: predicted winner, reasonable odds, top confidence."""
    candidates = []
    for row in rows:
        matchup = row["matchup"]
        pred = row["pred"]
        angles = row["angles"]
        f1, f2 = row["f1"], row["f2"]
        conf = row["confidence"]
        winner = pred.get("winner", "")

        if conf < config.VALUE_SLIP_MIN_CONFIDENCE:
            continue

        value = angles.get("value_pick") or angles.get("edge_pick") or {}
        pick_text = _format_pick(value.get("bet", ""), f1, f2)

        method = pred.get("method", "Dec")
        if not pick_text or not pick_matches_winner(pick_text, winner, f1, f2):
            pick_text, odds = _winner_ml_pick(winner, f1, f2, markets_by, matchup, method)
        else:
            odds = _enrich_odds(
                pick_text, matchup, value.get("odds"), markets_by,
                value.get("bet_type", "ml"), winner, method,
            )

        if not odds:
            pick_text, odds = _winner_ml_pick(winner, f1, f2, markets_by, matchup, method)
        if not odds or not leg_odds_ok(odds, getattr(config, "VALUE_SLIP_MAX_LEG_ODDS", 8.0)):
            continue

        reason = value.get("reason", pred.get("key_factor", "Model edge"))
        score = edge_score(conf, odds)
        candidates.append({
            "match": matchup,
            "pick": pick_text,
            "odds": odds,
            "reason": reason[:80] + "..." if len(reason) > 80 else reason,
            "_score": score,
            "_conf": conf,
        })

    candidates.sort(key=lambda x: (-x["_score"], -x["_conf"]))
    trimmed = []
    for leg in candidates:
        leg.pop("_score", None)
        leg.pop("_conf", None)
        trimmed.append(leg)
        if len(trimmed) >= config.PARLAY_MAX_LEGS:
            break

    # Drop lowest-confidence leg if combined odds too high
    while len(trimmed) > 1 and combined_odds(trimmed) > config.VALUE_SLIP_MAX_COMBINED_ODDS:
        trimmed.pop()
    return trimmed


def main():
    print("--- 🎫 STEP 7: PARLAY MAKER (EDGE COUPON ENGINE) ---")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception:
        print(f"❌ '{INPUT_FILE}' not found or invalid JSON. Run step 5 first.")
        sys.exit(1)

    markets_by, sources_by = _load_markets_by_matchup()
    rows = []

    for item in results:
        matchup = item.get("matchup", "")
        data = item.get("fight_brain_output", {})
        if "error" in data or not data:
            continue

        pred = data.get("prediction", {})
        viol = data.get("violence_score", 0)
        angles = data.get("betting_angles", {})
        fighters = matchup.split(" vs ")
        f1 = fighters[0].strip() if fighters else ""
        f2 = fighters[1].strip() if len(fighters) > 1 else ""
        confidence = _to_conf_int(pred.get("confidence", 0))

        rows.append({
            "matchup": matchup,
            "data": data,
            "pred": pred,
            "angles": angles,
            "f1": f1,
            "f2": f2,
            "confidence": confidence,
            "viol": viol if isinstance(viol, (int, float)) else 0,
        })

    print(f"📊 Analyzing {len(rows)} fights for betting angles...")

    safe_primary = [r for r in rows if r["confidence"] >= config.PARLAY_SAFE_CONFIDENCE]
    safe_fallback = [r for r in rows if r["confidence"] >= config.PARLAY_SAFE_CONFIDENCE_FALLBACK]

    viol_primary = [r for r in rows if r["viol"] >= config.PARLAY_VIOLENCE_SCORE]
    viol_fallback = [r for r in rows if r["viol"] >= config.PARLAY_VIOLENCE_SCORE_FALLBACK]

    safe_slip = _build_safe_candidates(safe_primary or safe_fallback, markets_by)
    violence_slip = _build_violence_candidates(viol_primary or viol_fallback, markets_by)
    value_slip = _build_value_candidates(rows, markets_by)

    # Source stamp on every leg — traceability for healthcheck
    for slip in (safe_slip, violence_slip, value_slip):
        for leg in slip:
            key = _norm_matchup_key(leg.get("match", ""))
            leg["odds_source"] = sources_by.get(key, "unknown")

    parlays = {
        "safe_slip": safe_slip,
        "violence_slip": violence_slip,
        "value_slip": value_slip,
        "metadata": {
            "total_analyzed": len(results),
            "markets_enriched": bool(markets_by),
            "safe_primary_count": len(safe_primary),
            "violence_primary_count": len(viol_primary),
            "value_candidates": len(value_slip),
            "combined_value_odds": combined_odds(value_slip),
        },
    }

    print(f"   ✅ Safe Picks: {len(safe_slip)} (primary threshold: {len(safe_primary)} fights)")
    print(f"   ✅ Violence Picks: {len(violence_slip)} (primary threshold: {len(viol_primary)} fights)")
    print(f"   ✅ Edge/Value Picks: {len(value_slip)} @ {parlays['metadata']['combined_value_odds']}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parlays, f, indent=4)
    stamp_stage("4_parlays")

    print(f"\n📁 Coupons saved to '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
