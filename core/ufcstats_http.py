"""
UFCStats HTTP helper — transparently solves the site's JS proof-of-work check.

As of mid-2026 ufcstats.com serves a "Checking your browser…" interstitial:
an inline SHA-256 proof-of-work (find n where sha256(nonce+':'+n) starts with
N zeros), POSTed to /__c, which sets a clearance cookie for the session.
Plain `requests.get()` therefore returns an empty 3 KB shell and every
scraper silently sees "no rows".

This module keeps ONE shared requests.Session, detects the challenge page,
solves the PoW in Python (difficulty 2 → ~256 hashes, negligible), retries,
and returns the real response. All UFCStats scraping in the project must go
through `fetch()`.
"""
import hashlib
import re
import time
from urllib.parse import urlsplit

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_session = None

_NONCE_RE = re.compile(r'var\s+nonce\s*=\s*"([^"]+)"')
_TARGET_RE = re.compile(r"new Array\((\d+)\s*\+\s*1\)\.join\('0'\)")


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def reset_session():
    """Drop the shared session (e.g., clearance cookie went stale)."""
    global _session
    _session = None


def is_challenge_page(text: str) -> bool:
    head = text[:2000] if text else ""
    return "Checking your browser" in head or '"/__c"' in (text or "")


def _solve_pow(nonce: str, zeros: int) -> int:
    prefix = "0" * zeros
    n = 0
    # Difficulty 2 → avg 256 hashes. Cap generously so a future difficulty
    # bump degrades gracefully instead of hanging the pipeline.
    limit = 16 ** (zeros + 3)
    while n < limit:
        if hashlib.sha256(f"{nonce}:{n}".encode()).hexdigest().startswith(prefix):
            return n
        n += 1
    raise RuntimeError(f"PoW not solved within {limit} attempts (difficulty {zeros})")


def _solve_challenge(text: str, session: requests.Session, url: str, headers: dict, timeout: int) -> bool:
    m_nonce = _NONCE_RE.search(text)
    if not m_nonce:
        print("   [PoW] WARNING: challenge page detected but nonce not found (script changed?)")
        return False
    m_target = _TARGET_RE.search(text)
    zeros = int(m_target.group(1)) if m_target else 2

    nonce = m_nonce.group(1)
    try:
        n = _solve_pow(nonce, zeros)
    except RuntimeError as e:
        print(f"   [PoW] WARNING: PoW failed: {e}")
        return False

    parts = urlsplit(url)
    challenge_url = f"{parts.scheme}://{parts.netloc}/__c"
    try:
        resp = session.post(
            challenge_url,
            data={"nonce": nonce, "n": str(n)},
            headers=headers,
            timeout=timeout,
        )
        return 200 <= resp.status_code < 300
    except Exception as e:
        print(f"   [PoW] WARNING: challenge POST failed: {e}")
        return False


def fetch(url: str, headers: dict = None, timeout: int = 15, max_challenge_solves: int = 2):
    """GET a UFCStats URL, transparently solving the browser-check PoW.

    Returns the requests.Response (which may still be a challenge page if
    solving failed — callers keep their normal 'no rows' handling).
    """
    session = get_session()
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update({k: v for k, v in headers.items() if v})

    resp = session.get(url, headers=merged, timeout=timeout)
    solves = 0
    while (
        resp.status_code == 200
        and is_challenge_page(resp.text)
        and solves < max_challenge_solves
    ):
        print("   [PoW] UFCStats browser-check detected - solving proof-of-work...")
        if not _solve_challenge(resp.text, session, url, merged, timeout):
            break
        solves += 1
        time.sleep(0.3)
        resp = session.get(url, headers=merged, timeout=timeout)
    return resp
