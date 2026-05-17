"""
OddsPortal.com odds feed (encrypted .dat endpoints).

When accessible, provides moneyline + over/under + some prop markets.
May return empty on datacenter IPs (Cloudflare shell) — still worth trying on production VPS/home IP.
"""
import base64
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import requests

from core.odds_converter import normalize_odds
from core.the_odds_api import merge_market_data

logger = logging.getLogger("FightIQ.OddsPortal")

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.hashes import SHA256

    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

# From OddsPortal app.js (Dec 2024 — update if decrypt fails)
_OP_PASSWORD = b"%RtR8AB&nWsh=AQC+v!=pgAe@dSQG3kQ"
_OP_SALT = b"orieC_jQQWRmhkPvR6u2kzXeTube6aYupiOddsPortal"

_IP_BLOCKED: Optional[bool] = None

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "deflate",
    "Referer": "https://www.oddsportal.com/",
    "X-Requested-With": "XMLHttpRequest",
}

# MMA on OddsPortal (football=1); discovered via feed trial / site structure
MMA_SPORT_ID = 28
MMA_VERSION_ID = 1


def _session():
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _get(url: str, timeout: int = 20) -> Optional[str]:
    try:
        try:
            from curl_cffi import requests as cffi_requests

            r = cffi_requests.get(url, headers=_HEADERS, impersonate="chrome", timeout=timeout)
        except Exception:
            r = _session().get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.text
    except Exception as e:
        logger.debug("OddsPortal GET failed %s: %s", url[:80], e)
        return None


def decrypt_feed(data: str) -> Optional[dict]:
    if not _CRYPTO_OK or not data:
        return None
    try:
        decoded = base64.b64decode(data).decode("utf-8", errors="ignore")
        if ":" not in decoded:
            return None
        encrypted_b64, key_hex = decoded.split(":", 1)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_b64)
        iv = bytes.fromhex(key_hex)
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=_OP_SALT,
            iterations=1000,
            backend=default_backend(),
        )
        aes_key = kdf.derive(_OP_PASSWORD)
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_bytes = decryptor.update(encrypted_bytes) + decryptor.finalize()
        decrypted = decrypted_bytes.decode("utf-8", errors="ignore")
        end = decrypted.rfind("}")
        if end != -1:
            decrypted = decrypted[: end + 1]
        return json.loads(decrypted)
    except Exception as e:
        logger.debug("OddsPortal decrypt failed: %s", e)
        return None


def fetch_feed_url(url: str) -> Optional[str]:
    return _get(url)


def _slugify_fight(f1: str, f2: str) -> List[str]:
    def slug(name):
        s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
        return s

    a, b = slug(f1), slug(f2)
    return [f"{a}-{b}", f"{b}-{a}"]


def _extract_feed_params(html: str) -> List[Tuple[str, str, str]]:
    """Return list of (version, sport, uid, xhash) from page HTML."""
    out = []
    # match-event/1-28-AbCdEf-1-2-xhash.dat
    for m in re.finditer(
        r"/feed/match-event/(\d+)-(\d+)-([A-Za-z0-9]+)-\d+-\d+-([A-Za-z0-9]+)\.dat",
        html or "",
    ):
        out.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    # xhashf encoded in page
    for m in re.finditer(r'xhashf":"([^"]+)"', html or ""):
        xh = m.group(1)
        if "%" in xh:
            xh = "".join(chr(int(p, 16)) for p in xh.split("%")[1:] if p)
        out.append((str(MMA_VERSION_ID), str(MMA_SPORT_ID), "", xh))
    return out


def find_match_page_url(f1: str, f2: str) -> Optional[str]:
    """Discover OddsPortal match page via search + weight-class slugs."""
    global _IP_BLOCKED
    if _IP_BLOCKED:
        return None

    queries = [
        f"site:oddsportal.com/mma {f1} {f2}",
        f"oddsportal.com mma {f1} vs {f2}",
    ]
    for q in queries:
        try:
            r = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q},
                headers={"User-Agent": _HEADERS["User-Agent"]},
                timeout=12,
            )
            for m in re.finditer(r'uddg=([^&"]+)', r.text):
                link = unquote(m.group(1))
                if "oddsportal.com/mma" in link and "/world/" in link:
                    if _name_match_page(link, f1, f2):
                        return link
        except Exception:
            pass

    weight_paths = [
        "bantamweight-ufc-men",
        "featherweight-ufc-men",
        "flyweight-ufc-men",
        "heavyweight-ufc-men",
        "light-heavyweight-ufc-men",
        "lightweight-ufc-men",
        "middleweight-ufc-men",
        "welterweight-ufc-men",
        "strawweight-ufc-women",
        "catchweight-ufc-men",
    ]
    for slug_pair in _slugify_fight(f1, f2):
        for wp in weight_paths:
            url = f"https://www.oddsportal.com/mma/world/{wp}/{slug_pair}/"
            html = _get(url)
            if html and len(html) > 20000 and _name_match_page(html, f1, f2):
                return url
    return None


def _name_match_page(text: str, f1: str, f2: str) -> bool:
    t = (text or "").lower()
    for name in (f1, f2):
        parts = [p for p in name.lower().split() if len(p) > 2]
        if not any(p in t for p in parts):
            return False
    return True


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _fighters_match(home: str, away: str, f1: str, f2: str) -> bool:
    h, a, n1, n2 = _norm(home), _norm(away), _norm(f1), _norm(f2)
    return (n1.split()[-1] in h or h in n1) and (n2.split()[-1] in a or a in n2)


def _parse_decrypted_to_markets(data: dict, f1: str, f2: str) -> dict:
    """Best-effort parse OddsPortal decrypted JSON into our market_data schema."""
    out: dict = {}
    if not isinstance(data, dict):
        return out

    blob = json.dumps(data).lower()
    # Walk for american odds patterns attached to labels
    ml_prices = []
    mov = {}
    rounds = {}

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if isinstance(v, (int, float)) and 1.01 <= float(v) <= 50:
                    # decimal already
                    _tag_price(kl, float(v), path)
                elif isinstance(v, str) and re.match(r"^[+-]?\d{2,4}$", v.strip()):
                    _tag_price(kl + " " + path, v.strip(), path)
                walk(v, kl)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, path)

    def _tag_price(label: str, price, path: str):
        lbl = f"{label} {path}".lower()
        dec = None
        if isinstance(price, (int, float)) and price < 50:
            dec = float(price)
        else:
            try:
                dec = normalize_odds(str(price).replace("+", ""), "american")["decimal"]
            except Exception:
                return
        if not dec or dec < 1.01:
            return
        if "ko" in lbl or "tko" in lbl:
            mov.setdefault("KO/TKO", normalize_odds(dec, "decimal"))
        elif "sub" in lbl:
            mov.setdefault("Submission", normalize_odds(dec, "decimal"))
        elif "dec" in lbl:
            mov.setdefault("Decision", normalize_odds(dec, "decimal"))
        elif "over" in lbl and "2.5" in lbl:
            rounds.setdefault("Over_2.5", normalize_odds(dec, "decimal"))
        elif "under" in lbl and "2.5" in lbl:
            rounds.setdefault("Under_2.5", normalize_odds(dec, "decimal"))
        elif _name_in_label(lbl, f1) or _name_in_label(lbl, f2):
            ml_prices.append((lbl, dec))

    def _name_in_label(lbl, fighter):
        parts = [p for p in fighter.lower().split() if len(p) > 2]
        return any(p in lbl for p in parts)

    walk(data)

    if ml_prices:
        # Assign fighter_a to f1 best guess
        f1_odds = f2_odds = None
        for lbl, dec in ml_prices:
            if _name_in_label(lbl, f1):
                f1_odds = dec
            elif _name_in_label(lbl, f2):
                f2_odds = dec
        if f1_odds and f2_odds:
            out["moneyline"] = {
                "fighter_a": normalize_odds(f1_odds, "decimal"),
                "fighter_b": normalize_odds(f2_odds, "decimal"),
            }

    if mov:
        out.setdefault("props", {})["method_of_victory"] = mov
    if rounds:
        out.setdefault("props", {})["total_rounds"] = rounds

    if not out and ("1x2" in blob or "moneyline" in blob or "home" in blob):
        logger.debug("OddsPortal parsed JSON but no markets mapped (structure may have changed)")

    return out


def markets_for_fight(f1: str, f2: str) -> dict:
    global _IP_BLOCKED
    if _IP_BLOCKED is True:
        return {}

    page_url = find_match_page_url(f1, f2)
    if not page_url:
        logger.debug("OddsPortal: no match page for %s vs %s", f1, f2)
        return {}

    html = _get(page_url)
    if not html or len(html) < 15000:
        _IP_BLOCKED = True
        logger.info(
            "OddsPortal: site blocked or empty from this IP (skipping further fights)"
        )
        return {}

    params = _extract_feed_params(html)
    if not params:
        logger.debug("OddsPortal: no feed params on page %s", page_url)
        return {}

    for version, sport, uid, xhash in params:
        if not uid or not xhash:
            continue
        feed_url = (
            f"https://www.oddsportal.com/feed/match-event/"
            f"{version}-{sport}-{uid}-1-2-{xhash}.dat"
        )
        raw = fetch_feed_url(feed_url)
        if not raw or len(raw) < 100:
            continue
        if raw.strip().startswith("<"):
            continue
        decrypted = decrypt_feed(raw)
        if not decrypted:
            continue
        markets = _parse_decrypted_to_markets(decrypted, f1, f2)
        if markets:
            logger.info("OddsPortal: markets for %s vs %s from %s", f1, f2, feed_url)
            return markets

    return {}


def enrich_fight(f1: str, f2: str, base: dict) -> Tuple[dict, bool]:
    extra = markets_for_fight(f1, f2)
    if not extra:
        return base or {}, False
    return merge_market_data(base or {}, extra), True
