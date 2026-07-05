"""
Pipeline stage stamping — lets downstream modules detect STALE inputs.

Problem this solves: modules communicate via JSON files in data/. When an
upstream module crashes without writing its output, the downstream module
used to happily read the file left over from a PREVIOUS event and generate
(and post!) content for the wrong card.

Each producer calls stamp_stage("<stage>", event_name) right after writing
its output file. Each consumer calls require_fresh_stage("<stage>") before
trusting its input; on mismatch/stale it exits non-zero so the orchestrator
aborts the pipeline instead of publishing garbage.
"""
import json
import os
import sys
import time

from core.paths import get_data_path

META_FILE = get_data_path("pipeline_meta.json")

try:
    import core.config as _config
    DEFAULT_MAX_AGE_HOURS = getattr(_config, "PIPELINE_STAGE_MAX_AGE_HOURS", 36)
except Exception:
    DEFAULT_MAX_AGE_HOURS = 36


def _load():
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_event() -> str:
    """Event name from 1_card.json ('' if unavailable)."""
    try:
        with open(get_data_path("1_card.json"), "r", encoding="utf-8") as f:
            return (json.load(f).get("event") or "").strip()
    except Exception:
        return ""


def stamp_stage(stage: str, event: str = None) -> None:
    """Record that <stage> output was just (re)generated for <event>."""
    meta = _load()
    meta[stage] = {
        "event": (current_event() if event is None else event) or "",
        "timestamp": time.time(),
    }
    try:
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠️ pipeline_meta could not be written: {e}")


def check_stage_fresh(stage: str, event: str = None, max_age_hours: float = None):
    """Return (ok: bool, reason: str) without exiting."""
    max_age = DEFAULT_MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    entry = _load().get(stage)
    if not entry:
        return False, f"stage '{stage}' has never been stamped (upstream never completed?)"
    age_h = (time.time() - float(entry.get("timestamp", 0))) / 3600.0
    if age_h > max_age:
        return False, f"stage '{stage}' output is {age_h:.1f}h old (max {max_age}h) — stale"
    expected = current_event() if event is None else event
    stamped = (entry.get("event") or "").strip()
    if expected and stamped and stamped != expected:
        return False, (
            f"stage '{stage}' output belongs to event '{stamped}' "
            f"but current card is '{expected}' — stale"
        )
    return True, "ok"


def require_fresh_stage(stage: str, event: str = None, max_age_hours: float = None) -> None:
    """Exit(1) if the given stage's output is missing, stale, or for another event."""
    ok, reason = check_stage_fresh(stage, event=event, max_age_hours=max_age_hours)
    if not ok:
        print(f"❌ STALE INPUT GUARD: {reason}")
        print("   Refusing to continue — rerun the upstream module first.")
        sys.exit(1)
