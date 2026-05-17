"""
Enrich fighter scout payloads for Fight Brain — quality proxies, injuries, matchup edges.
"""
import re

from core.numeric_safe import safe_float as _float, safe_pct as _pct

INJURY_KEYWORDS = (
    "injury", "injured", "withdraw", "replacement", "pull", "out of",
    "surgery", "torn", "acl", "mcl", "broken", "illness", "weight miss",
    "missed weight", "sakat", "sakatlık", "çekildi",
)


def _parse_reach(reach):
    if not reach:
        return None
    m = re.search(r"(\d+)", str(reach))
    return int(m.group(1)) if m else None


def _news_injury_flag(news_items) -> bool:
    if not news_items:
        return False
    for item in news_items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").lower()
        if any(k in title for k in INJURY_KEYWORDS):
            return True
    return False


def enrich_scout(scout: dict, news_for_fighter=None) -> dict:
    """Add derived analytics fields (not hallucinated rankings)."""
    if not scout:
        return scout
    out = dict(scout)
    rec = out.get("record", "0-0-0")
    try:
        parts = str(rec).replace(" ", "").split("-")
        w, l = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        w, l = int(out.get("wins") or 0), int(out.get("losses") or 0)
    total = w + l
    out["win_rate_pct"] = round(100.0 * w / total, 1) if total else 0
    out["total_fights"] = total
    out["finish_rate_pct"] = round(
        _float(out.get("KO_rate")) + _float(out.get("Sub_rate")),
        1,
    )
    out["ranking_proxy"] = round(
        min(100, out["win_rate_pct"] * 0.4 + total * 1.5 + _float(out.get("win_streak")) * 8),
        1,
    )
    out["injury_news_flag"] = _news_injury_flag(news_for_fighter or [])
    out["striking_differential"] = round(
        _float(out.get("SLpM")) - _float(out.get("SApM")), 2
    )
    return out


def build_matchup_context(scout1: dict, scout2: dict, news1=None, news2=None) -> dict:
    """Head-to-head context block for the AI prompt."""
    s1 = enrich_scout(scout1, news1)
    s2 = enrich_scout(scout2, news2)
    r1, r2 = _parse_reach(s1.get("reach")), _parse_reach(s2.get("reach"))
    reach_edge = None
    if r1 and r2:
        reach_edge = r1 - r2
    st1, st2 = (s1.get("stance") or "").lower(), (s2.get("stance") or "").lower()
    stance_note = ""
    if "southpaw" in st1 and "orthodox" in st2:
        stance_note = f"{s1.get('name')} southpaw vs orthodox — angle advantage potential."
    elif "southpaw" in st2 and "orthodox" in st1:
        stance_note = f"{s2.get('name')} southpaw vs orthodox — angle advantage potential."

    return {
        "reach_advantage_inches": reach_edge,
        "reach_favored": s1.get("name") if reach_edge and reach_edge > 1 else (
            s2.get("name") if reach_edge and reach_edge < -1 else None
        ),
        "stance_matchup_note": stance_note or "Orthodox mirror — no stance edge.",
        "quality_gap": round((s1.get("ranking_proxy", 50) or 50) - (s2.get("ranking_proxy", 50) or 50), 1),
        "momentum_edge": (
            s1.get("name")
            if (s1.get("win_streak", 0) or 0) > (s2.get("win_streak", 0) or 0)
            else s2.get("name")
            if (s2.get("win_streak", 0) or 0) > (s1.get("win_streak", 0) or 0)
            else "Even"
        ),
        "injury_flags": {
            s1.get("name", "F1"): s1.get("injury_news_flag", False),
            s2.get("name", "F2"): s2.get("injury_news_flag", False),
        },
    }
