"""
Optional tertiary odds source — The Odds API (https://the-odds-api.com).

Requires env THE_ODDS_API_KEY. Free tier: ~500 requests/month.
MMA coverage: moneyline (h2h) + totals (over/under rounds) from US/EU books when listed.
Does NOT replace Betist for Turkish method props — use when Betist is empty and BFO is ML-only.
"""
import logging
import os
import re
from typing import Dict, List, Optional

import requests

from core.odds_converter import normalize_odds
from core.numeric_safe import safe_float

logger = logging.getLogger("FightIQ.TheOddsAPI")

SPORT_KEY = "mma_mixed_martial_arts"
BASE_URL = "https://api.the-odds-api.com/v4"

_events_cache: Optional[List[dict]] = None


def _api_key() -> Optional[str]:
    return (os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY") or "").strip() or None


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").lower().strip())


def _fighters_match(home: str, away: str, f1: str, f2: str) -> bool:
    h, a = _norm_name(home), _norm_name(away)
    n1, n2 = _norm_name(f1), _norm_name(f2)
    if not all([h, a, n1, n2]):
        return False
    return (n1 in h or h in n1 or n1.split()[-1] in h) and (n2 in a or a in n2 or n2.split()[-1] in a)


def fetch_ufc_events(force: bool = False) -> List[dict]:
    global _events_cache
    if _events_cache is not None and not force:
        return _events_cache
    key = _api_key()
    if not key:
        return []
    url = f"{BASE_URL}/sports/{SPORT_KEY}/events"
    try:
        r = requests.get(url, params={"apiKey": key}, timeout=15)
        r.raise_for_status()
        data = r.json()
        _events_cache = data if isinstance(data, list) else []
        return _events_cache
    except Exception as e:
        logger.warning("The Odds API events fetch failed: %s", e)
        return []


def fetch_odds_for_event(event_id: str, markets: str = "h2h,totals") -> Optional[dict]:
    key = _api_key()
    if not key or not event_id:
        return None
    url = f"{BASE_URL}/sports/{SPORT_KEY}/events/{event_id}/odds"
    params = {
        "apiKey": key,
        "regions": "us,uk,eu",
        "markets": markets,
        "oddsFormat": "decimal",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("The Odds API odds fetch failed: %s", e)
        return None


def _best_decimal_outcomes(bookmakers: list, market_key: str) -> Dict[str, float]:
    """Average decimal across bookmakers for each outcome name."""
    buckets: Dict[str, List[float]] = {}
    for bk in bookmakers or []:
        for mkt in bk.get("markets") or []:
            if mkt.get("key") != market_key:
                continue
            for out in mkt.get("outcomes") or []:
                name = out.get("name") or ""
                price = safe_float(out.get("price"), 0)
                if name and 1.01 <= price <= 100:
                    buckets.setdefault(name, []).append(price)
    result = {}
    for name, prices in buckets.items():
        result[name] = round(sum(prices) / len(prices), 2)
    return result


def event_id_for_fight(f1: str, f2: str, events: List[dict]) -> Optional[str]:
    for ev in events or []:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        if _fighters_match(home, away, f1, f2) or _fighters_match(home, away, f2, f1):
            return ev.get("id")
    return None


def markets_for_fight(f1: str, f2: str) -> dict:
    """
    Return market_data fragment: moneyline + optional total_rounds props.
    Empty dict if no API key or no match.
    """
    events = fetch_ufc_events()
    eid = event_id_for_fight(f1, f2, events)
    if not eid:
        return {}

    payload = fetch_odds_for_event(eid)
    if not payload:
        return {}

    bookmakers = payload.get("bookmakers") or []
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")

    h2h = _best_decimal_outcomes(bookmakers, "h2h")
    totals = _best_decimal_outcomes(bookmakers, "totals")

    out = {}
    if h2h:
        # Map home/away to fighter_a/b relative to requested f1
        if _fighters_match(home, away, f1, f2):
            out["moneyline"] = {
                "fighter_a": normalize_odds(h2h.get(home), "decimal"),
                "fighter_b": normalize_odds(h2h.get(away), "decimal"),
            }
        else:
            out["moneyline"] = {
                "fighter_a": normalize_odds(h2h.get(away), "decimal"),
                "fighter_b": normalize_odds(h2h.get(home), "decimal"),
            }

    if totals:
        tr = {}
        for name, price in totals.items():
            nl = name.lower()
            point = ""
            m = re.search(r"([\d.]+)", name)
            if m:
                point = m.group(1)
            if "over" in nl:
                key = f"Over_{point}" if point else "Over_2.5"
                tr[key] = normalize_odds(price, "decimal")
            elif "under" in nl:
                key = f"Under_{point}" if point else "Under_2.5"
                tr[key] = normalize_odds(price, "decimal")
        if tr:
            out.setdefault("props", {})["total_rounds"] = tr

    return out


def merge_market_data(base: dict, extra: dict) -> dict:
    """Merge extra lines into base without overwriting Betist/BFO prices."""
    if not extra:
        return base or {}
    merged = dict(base or {})
    for key, val in extra.items():
        if key == "props" and isinstance(val, dict):
            props = merged.setdefault("props", {})
            for pk, pv in val.items():
                if pk not in props:
                    props[pk] = pv
                elif isinstance(pv, dict) and isinstance(props.get(pk), dict):
                    for ok, ov in pv.items():
                        if ok not in props[pk]:
                            props[pk][ok] = ov
        elif key not in merged or not merged.get(key):
            merged[key] = val
    return merged
