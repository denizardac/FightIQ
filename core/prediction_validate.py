"""
Post-process Fight Brain: one winner, best market per slip (ML / method / rounds / distance).
Never emit fake 0.0 odds — use catalog resolution or odds_available=false.
"""
import core.config as config
from core.market_catalog import (
    catalog_bets,
    format_bet_label,
    select_best_bet,
)
from core.odds_resolve import enrich_angle, resolve_pick_odds, winner_ml_odds
from core.parlay_logic import pick_matches_winner


def implied_probability(decimal_odds):
    if not decimal_odds or decimal_odds <= 1.0:
        return None
    return round(100.0 / decimal_odds, 1)


def _normalize_winner_name(winner: str, f1: str, f2: str) -> str:
    if not winner:
        return f1
    w = winner.strip().lower()
    if w in f1.lower() or f1.lower() in w:
        return f1
    if w in f2.lower() or f2.lower() in w:
        return f2
    parts = [p for p in w.split() if len(p) > 2]
    if parts and parts[-1] in f1.lower():
        return f1
    if parts and parts[-1] in f2.lower():
        return f2
    return winner


def _scout_for_winner(scout1, scout2, f1, f2, winner):
    if winner.strip().lower() in f1.strip().lower():
        return scout1 or {}
    return scout2 or {}


def _angle_from_option(opt, winner: str, reason: str) -> dict:
    if not opt:
        return {
            "bet": f"{winner} ML",
            "odds": None,
            "bet_type": "ml",
            "reason": reason,
            "odds_available": False,
        }
    return {
        "bet": format_bet_label(opt, winner),
        "odds": opt.odds,
        "bet_type": opt.bet_type,
        "market": opt.market,
        "reason": reason,
        "odds_available": True,
    }


def validate_and_unify(
    brain_output: dict,
    f1: str,
    f2: str,
    market_data: dict = None,
    scout1: dict = None,
    scout2: dict = None,
) -> dict:
    if not brain_output or not isinstance(brain_output, dict):
        return brain_output

    market_data = market_data or {}
    pred = brain_output.setdefault("prediction", {})
    angles = brain_output.setdefault("betting_angles", {})
    tweets = brain_output.setdefault("content_tweets", {})

    winner = _normalize_winner_name(pred.get("winner", ""), f1, f2)
    pred["winner"] = winner
    method = pred.get("method", "Dec")
    try:
        conf = max(1, min(10, int(pred.get("confidence", 5))))
    except (TypeError, ValueError):
        conf = 5
    pred["confidence"] = conf
    try:
        viol = int(brain_output.get("violence_score", 50))
    except (TypeError, ValueError):
        viol = 50

    sw = _scout_for_winner(scout1, scout2, f1, f2, winner)
    key_factor = pred.get("key_factor", "")
    catalog_count = len(catalog_bets(market_data, f1, f2, winner, method))

    safe_opt = select_best_bet(
        market_data, f1, f2, winner, method, conf, viol, sw,
        slip_kind="safe",
        odds_min=1.15,
        odds_max=getattr(config, "SAFE_SLIP_MAX_ODDS", 2.2),
    )
    # Value: if only ML on board, allow favorite ML even below 1.45
    value_min = getattr(config, "VALUE_SLIP_MIN_LEG_ODDS", 1.45)
    if catalog_count <= 2:
        value_min = 1.20
    value_opt = select_best_bet(
        market_data, f1, f2, winner, method, conf, viol, sw,
        slip_kind="value",
        odds_min=value_min,
        odds_max=getattr(config, "VALUE_SLIP_MAX_LEG_ODDS", 8.0),
    )
    viol_opt = select_best_bet(
        market_data, f1, f2, winner, method, conf, viol, sw,
        slip_kind="violence",
        odds_min=1.35,
        odds_max=5.0,
    )

    # Safe
    safe = angles.get("safe_pick") or {}
    if safe_opt and (
        not safe.get("bet")
        or not pick_matches_winner(safe.get("bet", ""), winner, f1, f2)
    ):
        safe = _angle_from_option(safe_opt, winner, safe.get("reason") or key_factor)
    safe = enrich_angle(safe, market_data, f1, f2, winner, method, allow_ml_fallback=True)

    # Value — prefer catalog edge pick, else AI angle resolved against board
    if value_opt:
        value = _angle_from_option(
            value_opt, winner, (angles.get("value_pick") or {}).get("reason") or key_factor
        )
    else:
        value = dict(angles.get("value_pick") or {})
        if not pick_matches_winner(value.get("bet", ""), winner, f1, f2):
            value = {"bet": f"{winner} ML", "bet_type": "ml", "reason": key_factor}
    value = enrich_angle(value, market_data, f1, f2, winner, method, allow_ml_fallback=True)

    # Violence — only keep priced totals/distance/KO lines
    violence = dict(angles.get("violence_pick") or {})
    if viol_opt:
        violence = _angle_from_option(
            viol_opt, winner, violence.get("reason") or f"Violence {viol}/100"
        )
    elif not violence.get("bet"):
        violence = {
            "bet": "Fight Does NOT Go Distance" if viol >= 65 else "Fight Goes the Distance",
            "bet_type": "distance_no" if viol >= 65 else "distance_yes",
            "reason": f"Violence index {viol}/100",
        }
    violence = enrich_angle(
        violence, market_data, f1, f2, winner, method, allow_ml_fallback=False
    )

    angles["safe_pick"] = safe
    angles["value_pick"] = value
    angles["violence_pick"] = violence

    canonical = value.get("bet", f"{winner} ML")
    can_odds = value.get("odds")
    if value.get("odds_available") and can_odds and float(can_odds) > 1.01:
        odds_snip = f" @ {round(float(can_odds), 2)}"
    else:
        odds_snip = ""
    tweets["betting_tweet"] = (
        f"Best bet: {canonical}{odds_snip}. {key_factor[:90]} #UFC #Betting"
    )[:275]

    wml = winner_ml_odds(market_data, f1, f2, winner)
    brain_output["market_context"] = {
        "markets_available": catalog_count,
        "winner_ml_odds": wml,
        "winner_implied_pct": implied_probability(wml),
        "canonical_bet": canonical,
        "canonical_odds": can_odds if value.get("odds_available") else None,
        "canonical_bet_type": value.get("bet_type"),
        "canonical_odds_available": bool(value.get("odds_available")),
    }
    brain_output["betting_angles"] = angles
    brain_output["content_tweets"] = tweets
    brain_output["prediction"] = pred
    return brain_output
