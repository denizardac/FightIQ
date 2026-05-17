"""Safe numeric parsing — never crash on N/A, --, or empty scout fields."""
from typing import Optional


def safe_float(val, default: float = 0.0) -> float:
    if val in (None, "", "N/A", "--", "n/a"):
        return default
    if isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("%", "").replace(",", ".")
    if s in ("", "N/A", "--", "n/a"):
        return default
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def safe_int(val, default: int = 0) -> int:
    try:
        return int(safe_float(val, default))
    except (TypeError, ValueError):
        return default


def safe_pct(val, default: float = 0.0) -> float:
    return safe_float(val, default)
