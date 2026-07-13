"""
Shared fighter-name matching — the single source of truth.

Historically five near-identical copies of "does this string name this
fighter" lived across live_wire, scorecard, odds_resolve, market_catalog and
parlay_logic; a fix in one never reached the others. Two distinct operations
live here now:

  * names_match(a, b)  — symmetric: do two names refer to the same person?
  * name_in(text, f)   — asymmetric: does fighter `f` appear inside `text`
                          (a bet label, pick string, etc.)?
"""
import re


def norm_name(name) -> str:
    """Lowercase, keep alphanumerics and single spaces, collapse runs."""
    s = "".join(ch for ch in str(name or "").lower() if ch.isalnum() or ch == " ")
    return re.sub(r"\s+", " ", s).strip()


def names_match(a, b) -> bool:
    """True if two fighter names refer to the same person (last-name tolerant).

    Guards against same-surname fighters on one card (common in MMA — e.g.
    two "Silva" or two "Nurmagomedov" bouts): a bare surname match is only
    accepted when the given names are also compatible, so
    "Umar Nurmagomedov" no longer cross-links to "Khabib Nurmagomedov".
    """
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    pa = [p for p in na.split() if len(p) > 2]
    pb = [p for p in nb.split() if len(p) > 2]
    if not (pa and pb):
        return False
    # Surnames must match.
    if pa[-1] != pb[-1]:
        return False
    # When both sides carry a distinct given name, it must be compatible.
    # (If we reached here, neither name is a substring of the other, so a
    # surname-only side would already have matched above.)
    if len(pa) >= 2 and len(pb) >= 2:
        ga, gb = pa[0], pb[0]
        return ga == gb or ga.startswith(gb) or gb.startswith(ga)
    return True


def name_in(text, fighter) -> bool:
    """True if `fighter` is named within `text` (label/pick string)."""
    if not text or not fighter:
        return False
    t, f = norm_name(text), norm_name(fighter)
    if not t or not f:
        return False
    if f in t or t in f:
        return True
    parts = [p for p in f.split() if len(p) > 2]
    return bool(parts) and parts[-1] in t
