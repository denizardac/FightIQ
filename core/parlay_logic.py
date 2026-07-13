"""
Shared parlay selection helpers — used by parlay_maker and social_director.
"""
import core.config as config


def pick_matches_winner(pick_text: str, winner: str, f1: str, f2: str) -> bool:
    """True if pick_text clearly backs the predicted winner."""
    if not pick_text or not winner:
        return False
    pt = pick_text.lower()
    w = winner.lower()
    if w in pt:
        return True
    # Last-name match (handles "Costa ML" vs "Melquizael Costa")
    w_parts = [p for p in w.split() if len(p) > 2]
    if w_parts and w_parts[-1] in pt:
        return True
    f1l, f2l = f1.lower(), f2.lower()
    if w in f1l or f1l in w:
        return f1l in pt or any(p in pt for p in f1l.split() if len(p) > 2)
    if w in f2l or f2l in w:
        return f2l in pt or any(p in pt for p in f2l.split() if len(p) > 2)
    return False


def leg_odds_ok(odds, max_odds=None) -> bool:
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return False
    cap = max_odds if max_odds is not None else config.VALUE_SLIP_MAX_LEG_ODDS
    return config.VALUE_SLIP_MIN_LEG_ODDS <= o <= cap


def combined_odds(legs) -> float:
    total = 1.0
    for leg in legs:
        try:
            o = float(leg.get("odds") or 0)
        except (TypeError, ValueError):
            continue
        if o > 1.0:
            total *= o
    return round(total, 2)


def edge_score(confidence: int, odds: float) -> float:
    """Rank value legs: higher confidence + reasonable plus-money."""
    conf = max(0, min(10, int(confidence or 0)))
    try:
        o = float(odds or 1.85)
    except (TypeError, ValueError):
        o = 1.85
    # Sweet spot: slight plus money with strong model confidence
    odds_bonus = 0.0
    if 1.55 <= o <= 2.80:
        odds_bonus = 0.15
    elif 2.80 < o <= config.VALUE_SLIP_MAX_LEG_ODDS:
        odds_bonus = 0.05
    return conf + odds_bonus


def trim_slip(legs, max_legs=None):
    cap = max_legs or config.PARLAY_MAX_LEGS
    return legs[:cap]
