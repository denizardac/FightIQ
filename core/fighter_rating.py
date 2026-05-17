"""
Matchup-relative fighter ratings (bars on Versus cards).
Avoids absurd 96 vs 49 unless stats truly dominate; anchored to 50/50.
"""
import re


def _pct(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return default


def _float(val, default=0.0):
    try:
        return float(val or default)
    except (TypeError, ValueError):
        return default


def _parse_reach_inches(reach) -> float:
    if not reach:
        return 0.0
    s = str(reach)
    m = re.search(r"(\d+)", s)
    return float(m.group(1)) if m else 0.0


def _raw_dimensions(scout: dict, deep: dict) -> dict:
    st = scout or {}
    d = deep or {}
    slpm = _float(st.get("SLpM"))
    sapm = _float(st.get("SApM"))
    s_acc = _pct(st.get("Str_Acc"))
    s_def = _pct(st.get("Str_Def"))
    td = _float(st.get("TD_Avg"))
    sub = _float(st.get("Sub_Avg"))
    td_acc = _pct(st.get("TD_Acc"))
    td_def = _pct(st.get("TD_Def"))
    ko = _float(d.get("ko_rate"))
    subr = _float(d.get("sub_rate"))
    decr = _float(d.get("dec_rate"))
    avg_sec = _float(d.get("avg_fight_time_sec"), 540)
    wins = int(d.get("wins") or 0)
    losses = int(d.get("losses") or 0)
    total = wins + losses + int(d.get("draws") or 0)
    win_rate = (wins / total * 100) if total else 50.0
    reach = _parse_reach_inches(st.get("reach") or d.get("reach"))
    fr = int(d.get("first_round_finishes") or 0)

    striking = slpm * 8.0 + s_acc * 0.35 + max(0, slpm - sapm) * 6.0 + s_def * 0.15
    grappling = td * 18.0 + sub * 14.0 + td_acc * 0.12 + subr * 0.25
    power = ko * 0.55 + slpm * 2.5 + fr * 4.0
    cardio = min(avg_sec / 7.5, 100) + decr * 0.2 + win_rate * 0.1
    durability = s_def * 0.55 + max(0, 6.0 - sapm) * 5.0 + td_def * 0.2
    experience = min(100, total * 2.2 + wins * 0.5)

    return {
        "striking": striking,
        "grappling": grappling,
        "power": power,
        "cardio": cardio,
        "durability": durability,
        "experience": experience,
        "reach": reach,
    }


def _pair_bars(score_a: float, score_b: float, max_spread: float = 14.0) -> tuple:
    """
    Map two raw scores to bar values centered at 50.
    max_spread=14 → typical range 36–64; extreme mismatch up to 28–72.
    """
    diff = score_a - score_b
    spread = min(max_spread, abs(diff) * 0.35)
    if diff >= 0:
        return round(50 + spread), round(50 - spread)
    return round(50 - spread), round(50 + spread)


def compute_matchup_bars(scout1: dict, scout2: dict, deep1: dict, deep2: dict) -> dict:
    """
    Returns {fighter1: {power, striking, grappling, stamina, chin, technique}, fighter2: {...}}
    technique = striking craft; chin = durability.
    """
    r1 = _raw_dimensions(scout1, deep1)
    r2 = _raw_dimensions(scout2, deep2)

    p1, p2 = _pair_bars(r1["power"], r2["power"])
    s1, s2 = _pair_bars(r1["striking"], r2["striking"])
    g1, g2 = _pair_bars(r1["grappling"], r2["grappling"])
    c1, c2 = _pair_bars(r1["cardio"], r2["cardio"])
    d1, d2 = _pair_bars(r1["durability"], r2["durability"])
    t1, t2 = _pair_bars(r1["striking"] * 0.6 + r1["experience"] * 0.4, r2["striking"] * 0.6 + r2["experience"] * 0.4)

    return {
        "fighter1": {
            "power": p1,
            "striking": s1,
            "grappling": g1,
            "stamina": c1,
            "chin": d1,
            "technique": t1,
        },
        "fighter2": {
            "power": p2,
            "striking": s2,
            "grappling": g2,
            "stamina": c2,
            "chin": d2,
            "technique": t2,
        },
    }


def style_one_liner(scout: dict, deep: dict) -> str:
    """Deterministic 3–4 word style tag from stats."""
    r = _raw_dimensions(scout, deep)
    if r["grappling"] > r["striking"] + 8 and r["grappling"] > 55:
        return "Grappling Threat"
    if r["power"] > 58 and r["striking"] > 50:
        return "Power Striker"
    if r["striking"] > 58:
        return "Volume Striker"
    if r["cardio"] > 58:
        return "Pressure Fighter"
    return "Balanced Scrapper"
