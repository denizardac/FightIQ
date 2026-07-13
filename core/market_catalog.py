"""
Parse all available betting markets and pick the best bet per strategy (not ML-only).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from core.odds_converter import american_to_decimal
from core.name_match import name_in as _name_in


def to_decimal(val) -> Optional[float]:
    if val is None or val == "" or val == 0:
        return None
    if isinstance(val, dict):
        if val.get("decimal") is not None:
            try:
                return round(float(val["decimal"]), 2)
            except (TypeError, ValueError):
                pass
        if val.get("american") is not None:
            try:
                return round(american_to_decimal(str(val["american"]).replace("+", "")), 2)
            except Exception:
                pass
        return None
    if isinstance(val, (int, float)):
        fv = float(val)
        if fv > 50:
            try:
                return round(american_to_decimal(int(fv)), 2)
            except Exception:
                pass
        if 1.01 <= fv <= 100:
            return round(fv, 2)
    if isinstance(val, str):
        s = val.strip().replace(",", ".")
        try:
            fv = float(s)
            if 1.01 <= fv <= 100:
                return round(fv, 2)
        except ValueError:
            pass
        if re.match(r"^[+-]\d{3,}$", s):
            try:
                return round(american_to_decimal(s), 2)
            except Exception:
                pass
    return None


@dataclass
class BetOption:
    market: str
    label: str
    odds: float
    bet_type: str  # ml, ko, sub, dec, over, under, distance_yes, distance_no, other
    aligns_winner: bool = True
    risk: str = "medium"  # low, medium, high
    edge_hint: float = 0.0


def _safe_rate(val) -> float:
    if val in (None, "", "N/A", "--"):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _classify_bet_type(label: str, market: str) -> str:
    blob = f"{market} {label}".lower()
    if "under" in blob and ("round" in blob or "raund" in blob or "2.5" in blob):
        return "under"
    if "over" in blob and ("round" in blob or "raund" in blob or "2.5" in blob):
        return "over"
    if "goes the distance" in blob or "go distance" in blob or "mesafe" in blob:
        return "distance_yes"
    if "not go" in blob or "doesn't go" in blob or "does not go" in blob:
        return "distance_no"
    if "sub" in blob or "choke" in blob:
        return "sub"
    if "ko" in blob or "tko" in blob or "knockout" in blob:
        return "ko"
    if "dec" in blob or "decision" in blob or "points" in blob:
        return "dec"
    if "moneyline" in blob or " ml" in blob or blob.endswith(" ml"):
        return "ml"
    return "other"


def catalog_bets(
    market_data: dict,
    f1: str,
    f2: str,
    winner: str,
    predicted_method: str = "Dec",
) -> List[BetOption]:
    """Flatten every priced outcome we can find."""
    options: List[BetOption] = []
    if not isinstance(market_data, dict):
        return options

    wl = winner.lower()
    method_l = (predicted_method or "").lower()

    def add(market: str, label: str, odds_raw, bet_type: str = None, aligns=True, risk="medium"):
        dec = to_decimal(odds_raw)
        if not dec or dec < 1.01:
            return
        bt = bet_type or _classify_bet_type(label, market)
        options.append(
            BetOption(
                market=market,
                label=label.strip(),
                odds=dec,
                bet_type=bt,
                aligns_winner=aligns,
                risk=risk,
            )
        )

    # Nested BFO props
    props = market_data.get("props") or {}
    if isinstance(props, dict):
        mov = props.get("method_of_victory") or {}
        if isinstance(mov, dict):
            for outcome, oval in mov.items():
                ol = str(outcome).lower()
                aligns = True
                bt = "ko" if "ko" in ol else "sub" if "sub" in ol else "dec"
                if method_l.startswith("ko") and bt != "ko":
                    aligns = False
                elif "sub" in method_l and bt != "sub":
                    aligns = False
                elif "dec" in method_l and bt != "dec":
                    aligns = False
                add("Method of Victory", outcome, oval, bt, aligns=aligns, risk="medium")

        tr = props.get("total_rounds") or {}
        if isinstance(tr, dict):
            for outcome, oval in tr.items():
                add("Total Rounds", outcome, oval, _classify_bet_type(str(outcome), "rounds"), risk="medium")

    skip_keys = {"props", "line_movement", "betist_odds"}
    for mname, outcomes in market_data.items():
        if mname in skip_keys or not isinstance(outcomes, dict):
            continue
        mlow = str(mname).lower()

        if mlow in ("moneyline", "kazanır", "1x2", "match winner"):
            for oname, oval in outcomes.items():
                if str(oname).lower() in skip_keys:
                    continue
                oname_l = str(oname).lower()
                if oname_l in ("fighter_a", "a"):
                    label, aligns = f"{f1} ML", winner.lower() in f1.lower()
                elif oname_l in ("fighter_b", "b"):
                    label, aligns = f"{f2} ML", winner.lower() in f2.lower()
                else:
                    label = f"{oname} ML" if "ml" not in oname_l else str(oname)
                    aligns = _name_in(str(oname), winner)
                add(mname, label, oval, "ml", aligns=aligns, risk="low" if aligns and to_decimal(oval) and to_decimal(oval) < 1.75 else "medium")
            continue

        # Turkish / generic prop markets from Betist
        for oname, oval in outcomes.items():
            if str(oname).lower() in skip_keys:
                continue
            label = f"{oname}"
            if mname not in label:
                label = f"{oname} ({mname})"
            bt = _classify_bet_type(label, mname)
            aligns = True
            if bt == "ml":
                aligns = _name_in(str(oname), winner) or _name_in(str(oname), f1) and wl in f1.lower() or _name_in(str(oname), f2) and wl in f2.lower()
            elif bt in ("ko", "sub", "dec"):
                aligns = _name_in(str(oname), winner) or not _name_in(str(oname), f1) and not _name_in(str(oname), f2)
            add(mname, label, oval, bt, aligns=aligns, risk="medium")

    return options


def _score_option(
    opt: BetOption,
    confidence: int,
    violence_score: int,
    ko_rate: float,
    sub_rate: float,
    dec_rate: float,
    slip_kind: str,
) -> float:
    """Higher = better fit for this slip type."""
    implied = 100.0 / opt.odds if opt.odds > 1 else 50
    conf = max(1, min(10, confidence))
    score = 0.0

    if slip_kind == "safe":
        if opt.risk == "low" and opt.bet_type == "ml" and opt.aligns_winner:
            score += 30 + conf * 2
        if opt.bet_type == "dec" and dec_rate > 45 and opt.aligns_winner:
            score += 25 + conf
        if opt.bet_type == "distance_yes" and violence_score < 55:
            score += 20
        if opt.odds and 1.25 <= opt.odds <= 1.85:
            score += 8
        score -= max(0, opt.odds - 2.0) * 5

    elif slip_kind == "value":
        if not opt.aligns_winner and opt.bet_type == "ml":
            return -999
        if opt.bet_type in ("ko", "sub", "dec") and opt.aligns_winner:
            stat_boost = ko_rate if opt.bet_type == "ko" else sub_rate if opt.bet_type == "sub" else dec_rate
            score += stat_boost * 0.35 + conf * 3
        if opt.bet_type in ("over", "distance_no") and violence_score >= 65:
            score += violence_score * 0.25 + conf * 2
        if opt.bet_type in ("under", "distance_yes") and violence_score < 50:
            score += (100 - violence_score) * 0.2 + conf
        if opt.bet_type == "ml" and opt.aligns_winner:
            score += conf * 2.5
        # Prefer plus money with edge
        if 1.55 <= opt.odds <= 4.5:
            score += (opt.odds - 1.0) * 4
        if opt.odds > 6.0:
            score += 5  # allow one longshot if stats support
        score += (50 - implied) * 0.15 if implied < 45 else 0

    elif slip_kind == "violence":
        if opt.bet_type in ("over", "distance_no", "ko"):
            score += violence_score * 0.4
        if opt.bet_type in ("under", "distance_yes"):
            score += (100 - violence_score) * 0.4
        if opt.bet_type == "ko" and violence_score >= 70:
            score += 15
        if 1.5 <= opt.odds <= 3.0:
            score += 5

    return score


def select_best_bet(
    market_data: dict,
    f1: str,
    f2: str,
    winner: str,
    method: str,
    confidence: int,
    violence_score: int,
    scout_winner: dict,
    slip_kind: str,
    odds_min: float = 1.20,
    odds_max: float = 8.0,
) -> Optional[BetOption]:
    ko = _safe_rate(scout_winner.get("KO_rate"))
    sub = _safe_rate(scout_winner.get("Sub_rate"))
    dec = _safe_rate(scout_winner.get("Dec_rate"))

    options = catalog_bets(market_data, f1, f2, winner, method)
    if not options:
        return None

    best = None
    best_score = -9999
    for opt in options:
        if opt.odds < odds_min or opt.odds > odds_max:
            continue
        if slip_kind in ("safe", "value") and opt.bet_type == "ml" and not opt.aligns_winner:
            continue
        # Violence slips use totals/method/distance — not opponent moneyline
        if slip_kind == "violence" and opt.bet_type == "ml":
            continue
        sc = _score_option(opt, confidence, violence_score, ko, sub, dec, slip_kind)
        if sc > best_score:
            best_score = sc
            best = opt
    return best


def format_bet_label(opt: BetOption, winner: str) -> str:
    """Human-readable pick for tickets/tweets."""
    if not opt:
        return f"{winner} ML"
    lbl = opt.label
    if opt.bet_type == "ml":
        return lbl if "ml" in lbl.lower() else f"{lbl}"
    if opt.bet_type in ("ko", "sub", "dec"):
        if _name_in(lbl, winner):
            return lbl
        method_word = {"ko": "KO/TKO", "sub": "Submission", "dec": "Decision"}[opt.bet_type]
        return f"{winner} by {method_word}"
    return lbl


def summarize_markets_for_prompt(market_data: dict, f1: str, f2: str) -> str:
    """Compact list for Gemini — every priced line."""
    lines = []
    for opt in catalog_bets(market_data, f1, f2, f1, "Dec"):
        lines.append(f"  - [{opt.market}] {opt.label} @ {opt.odds}")
    if not lines:
        return "  (No markets scraped — use stats-only picks and set odds 0.0)"
    return "\n".join(lines[:40])
