"""
Resolve decimal odds for a pick from scraped market_data (catalog-backed).
Never invent prices — returns None when no priced line exists.
"""
import re
from typing import Optional, Tuple

from core.market_catalog import catalog_bets, to_decimal, format_bet_label
from core.numeric_safe import safe_float


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _name_in(text: str, fighter: str) -> bool:
    if not text or not fighter:
        return False
    t, f = _norm(text), _norm(fighter)
    if f in t or t in f:
        return True
    parts = [p for p in f.split() if len(p) > 2]
    return bool(parts) and parts[-1] in t


def winner_ml_odds(market_data: dict, f1: str, f2: str, winner: str) -> Optional[float]:
    for opt in catalog_bets(market_data or {}, f1, f2, winner, "Dec"):
        if opt.bet_type == "ml" and opt.aligns_winner:
            return opt.odds
    return None


def _match_pick_to_option(pick_text: str, bet_type: str, options, winner: str, f1: str, f2: str):
    if not options:
        return None
    pt = _norm(pick_text)
    bt = (bet_type or "").lower()

    # Exact / substring on label
    for opt in options:
        if _norm(opt.label) in pt or pt in _norm(opt.label):
            return opt

    # Bet type + winner alignment
    typed = [o for o in options if o.bet_type == bt] if bt else []
    if bt == "ml":
        for o in typed:
            if o.aligns_winner and _name_in(o.label, winner):
                return o
    elif bt in ("ko", "sub", "dec"):
        for o in typed:
            if o.aligns_winner or _name_in(o.label, winner):
                return o
        for o in typed:
            return o
    elif bt in ("over", "under", "distance_yes", "distance_no"):
        for o in typed:
            if bt in o.bet_type:
                return o
        for o in options:
            if o.bet_type == bt:
                return o

    # Distance wording
    if "not go" in pt or "doesn't go" in pt or "does not go" in pt:
        for o in options:
            if o.bet_type == "distance_no":
                return o
    if "goes the distance" in pt or "go distance" in pt:
        for o in options:
            if o.bet_type == "distance_yes":
                return o
    if "over" in pt and "2.5" in pt:
        for o in options:
            if o.bet_type == "over":
                return o
    if "under" in pt and "2.5" in pt:
        for o in options:
            if o.bet_type == "under":
                return o

    return None


# Max relative deviation for accepting an AI-quoted price against the board.
AI_ODDS_BOARD_TOLERANCE = 0.05


def resolve_pick_odds(
    pick_text: str,
    bet_type: str,
    market_data: dict,
    f1: str,
    f2: str,
    winner: str,
    method: str = "Dec",
    ai_odds=None,
) -> Tuple[Optional[float], Optional[str], bool]:
    """
    Returns (decimal_odds, matched_label, odds_available).

    HALLUCINATION GUARD: the model's quoted price (ai_odds) is NEVER trusted
    on its own — it used to pass straight through if it merely looked like a
    plausible decimal, which put invented "KO @ 4.4" props on Twitter. Now the
    board is authoritative: ai_odds only helps pick between board options when
    it matches one of their prices within ±5%. No board price → no odds.
    """
    options = catalog_bets(market_data or {}, f1, f2, winner, method)

    # 1) Direct board match on label / bet type — authoritative price
    opt = _match_pick_to_option(pick_text, bet_type, options, winner, f1, f2)
    if opt and opt.odds:
        return opt.odds, format_bet_label(opt, winner), True

    # 2) AI-quoted price accepted ONLY if it matches a real board price ±5%
    dec = to_decimal(ai_odds)
    if dec and options:
        for o in options:
            if not o.odds:
                continue
            if abs(o.odds - dec) / o.odds <= AI_ODDS_BOARD_TOLERANCE:
                return o.odds, format_bet_label(o, winner), True

    # 3) ML fallback for winner-side picks when prop line missing
    if bet_type in ("ml", "ko", "sub", "dec", "", None) and _name_in(pick_text, winner):
        ml = winner_ml_odds(market_data, f1, f2, winner)
        if ml:
            return ml, f"{winner} ML", True

    return None, pick_text, False


def enrich_angle(
    angle: dict,
    market_data: dict,
    f1: str,
    f2: str,
    winner: str,
    method: str = "Dec",
    allow_ml_fallback: bool = True,
) -> dict:
    """Attach resolved odds; never leave fake 0.0."""
    if not angle:
        angle = {}
    out = dict(angle)
    pick = out.get("bet", "")
    bt = out.get("bet_type", "ml")
    dec, label, ok = resolve_pick_odds(
        pick, bt, market_data, f1, f2, winner, method, out.get("odds")
    )
    if ok and dec:
        out["odds"] = dec
        out["bet"] = label or pick
        out["odds_available"] = True
    else:
        out["odds"] = None
        out["odds_available"] = False
        if allow_ml_fallback and _name_in(pick, winner):
            ml = winner_ml_odds(market_data, f1, f2, winner)
            if ml:
                out["odds"] = ml
                out["bet"] = f"{winner} ML"
                out["bet_type"] = "ml"
                out["odds_available"] = True
                out["odds_note"] = "prop_unavailable_used_ml"
    return out
