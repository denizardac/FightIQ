"""
Action Network UFC odds page — rich JSON in __NEXT_DATA__ (moneyline from many books).
https://www.actionnetwork.com/ufc/odds
"""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import requests

from core.odds_converter import normalize_odds
from core.the_odds_api import merge_market_data

logger = logging.getLogger("FightIQ.ActionNetwork")

URL = "https://www.actionnetwork.com/ufc/odds"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_cache: Optional[dict] = None


def _load_page() -> Optional[dict]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        r = requests.get(URL, headers=_HEADERS, timeout=30)
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text,
            re.S,
        )
        if not m:
            return None
        _cache = json.loads(m.group(1))
        return _cache
    except Exception as e:
        logger.warning("Action Network fetch failed: %s", e)
        return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _name_match(full_name: str, target: str) -> bool:
    if not full_name or not target:
        return False
    fn, t = _norm(full_name), _norm(target)
    if t in fn or fn in t:
        return True
    return t.split()[-1] in fn or fn.split()[-1] in t


def _american_to_decimal(am) -> Optional[float]:
    try:
        v = int(am)
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    if v > 0:
        return round(1 + v / 100.0, 2)
    return round(1 + 100.0 / abs(v), 2)


def _find_competition(f1: str, f2: str, data: dict) -> Optional[dict]:
    sb = (data.get("props") or {}).get("pageProps", {}).get("scoreboardResponse") or {}
    for comp in sb.get("competitions") or []:
        names = []
        for c in comp.get("competitors") or []:
            p = c.get("player") or {}
            names.append(p.get("full_name") or "")
        if any(_name_match(n, f1) for n in names) and any(_name_match(n, f2) for n in names):
            return comp
    return None


def _avg_ml(comp: dict, f1: str, f2: str) -> Dict[str, float]:
    """Average american ML across books per fighter."""
    buckets: Dict[str, List[float]] = {f1: [], f2: []}
    markets = comp.get("markets") or {}
    for _book, book in markets.items():
        if not isinstance(book, dict):
            continue
        event = book.get("event") or {}
        for row in event.get("moneyline") or []:
            if not isinstance(row, dict):
                continue
            odds_am = row.get("odds")
            dec = _american_to_decimal(odds_am)
            if not dec:
                continue
            cid = row.get("competitor_id")
            for c in comp.get("competitors") or []:
                if c.get("id") != cid:
                    continue
                pname = (c.get("player") or {}).get("full_name", "")
                if _name_match(pname, f1):
                    buckets[f1].append(dec)
                elif _name_match(pname, f2):
                    buckets[f2].append(dec)
    out = {}
    for fighter, prices in buckets.items():
        if prices:
            out[fighter] = round(sum(prices) / len(prices), 2)
    return out


def markets_for_fight(f1: str, f2: str) -> dict:
    data = _load_page()
    if not data:
        return {}
    comp = _find_competition(f1, f2, data)
    if not comp:
        return {}
    avg = _avg_ml(comp, f1, f2)
    if len(avg) < 2:
        return {}
    return {
        "moneyline": {
            "fighter_a": normalize_odds(avg[f1], "decimal"),
            "fighter_b": normalize_odds(avg[f2], "decimal"),
        }
    }


def enrich_fight(f1: str, f2: str, base: dict) -> Tuple[dict, bool]:
    extra = markets_for_fight(f1, f2)
    if not extra:
        return base or {}, False
    merged = merge_market_data(base or {}, extra)
    logger.info("Action Network ML enriched %s vs %s", f1, f2)
    return merged, True
