"""
Pipeline health-check: verifies all expected outputs exist after a LIVE run.

Run at the very end of core/main.py. Surfaces silent failures the rest of
the pipeline tolerates (missing odds for a fight, missing portrait for
a fighter, etc.) so we can fix them before the bot wakes up.

Exit code is informational only — main.py decides what to do with it.

Usage:
    python3 -m tools.healthcheck
"""
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

# Always load .env from project root (cron cwd may be /root)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from core.paths import get_data_path, VISUALS_DIR, ASSETS_DIR, PROJECT_ROOT
from core.naming import versus_basename
from core.twitter_client import twitter_credentials_status


def _load(name):
    p = get_data_path(name)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _safe(name):
    return name.replace(" ", "_").lower()


def check_card_coverage():
    card = _load("1_card.json")
    if not card or card.get("status") != "LIVE":
        return {"skipped": True, "reason": "no LIVE card"}

    fights = card.get("fights", [])
    final = _load("2_data_final.json") or []
    odds_data = _load("2_data_with_odds.json") or []
    brain = _load("3_results.json") or []

    final_pairs = {tuple(sorted([f["fighters"][0], f["fighters"][1]])) for f in final
                   if isinstance(f, dict) and "fighters" in f}
    odds_pairs = {tuple(sorted([f["fighters"][0], f["fighters"][1]])) for f in odds_data
                  if isinstance(f, dict) and "fighters" in f
                  and f.get("odds_confidence") in ("high", "medium")}
    brain_pairs = {tuple(sorted(item["matchup"].split(" vs ")))
                   for item in brain if isinstance(item, dict) and " vs " in item.get("matchup", "")}

    img_cache = os.path.join(ASSETS_DIR, "images_cache")
    missing_imgs = []
    for fight in fights:
        for fighter in (fight.get("f1"), fight.get("f2")):
            if not fighter:
                continue
            if not os.path.exists(os.path.join(img_cache, f"{_safe(fighter)}.png")):
                missing_imgs.append(fighter)

    issues = {
        "fights_total":           len(fights),
        "missing_deep_stats":     [],
        "missing_odds":           [],
        "missing_ai_brain":       [],
        "missing_portraits":      missing_imgs,
        "missing_versus_cards":   [],
    }
    for fight in fights:
        pair = tuple(sorted([fight.get("f1", ""), fight.get("f2", "")]))
        if pair not in final_pairs:
            issues["missing_deep_stats"].append(" vs ".join(pair))
        if pair not in odds_pairs:
            issues["missing_odds"].append(" vs ".join(pair))
        if pair not in brain_pairs:
            issues["missing_ai_brain"].append(" vs ".join(pair))

        card_paths = [
            os.path.join(VISUALS_DIR, versus_basename(fight.get("f1", ""), fight.get("f2", ""))),
            os.path.join(VISUALS_DIR, versus_basename(fight.get("f2", ""), fight.get("f1", ""))),
        ]
        if not any(os.path.exists(p) for p in card_paths):
            issues["missing_versus_cards"].append(f"{fight.get('f1')} vs {fight.get('f2')}")

    return issues


def check_content_safety():
    """Pre-publication consistency checks (Phase 6 guard layer).

    - unsourced_odds: a published-ready price with no scraper source stamp
      (the invented-odds signature)
    - duplicate_spotlight: spotlight_ready text was already posted on an
      earlier day (repeat-content signature)
    - inactive_spotlight: spotlight fighter hasn't fought in ~24 months
    """
    import hashlib
    from datetime import datetime

    issues = {"unsourced_odds": [], "duplicate_spotlight": False,
              "inactive_spotlight": None}

    brain = _load("3_results.json") or []
    for item in brain if isinstance(brain, list) else []:
        angles = (item.get("fight_brain_output") or {}).get("betting_angles") or {}
        for key in ("safe_pick", "value_pick", "violence_pick"):
            a = angles.get(key) or {}
            if a.get("odds_available") and (a.get("odds_source") in (None, "", "unknown")):
                issues["unsourced_odds"].append(f"{item.get('matchup','?')}:{key}")

    spotlight = _load("spotlight_ready.json") or {}
    thread = spotlight.get("thread") or []
    if thread:
        h = hashlib.sha256(str(thread[0]).strip().lower().encode()).hexdigest()[:16]
        hashes = _load("content_hashes.json") or {}
        seen = hashes.get(h)
        today = datetime.today().strftime("%Y-%m-%d")
        if seen and seen != today:
            issues["duplicate_spotlight"] = True

    lfy = spotlight.get("last_fight_year")
    if lfy:
        try:
            if int(lfy) < datetime.today().year - 2:
                issues["inactive_spotlight"] = f"{spotlight.get('fighter')} (last fight {lfy})"
        except (TypeError, ValueError):
            pass

    return issues


def check_live_wire_readiness():
    """Preflight for fight-night Live Wire (scraping + Twitter)."""
    from datetime import datetime, timedelta

    card = _load("1_card.json") or {}
    tw = twitter_credentials_status()
    report = {
        "fight_night_today": False,
        "event_url": card.get("url"),
        "twitter_official_api": tw["official_api"],
        "twitter_cookies": tw["cookies"],
        "twitter_backend": tw["backend"],
        "twitter_ready": tw["ready"],
        "scrape_ok": False,
        "finished_fights": 0,
        "gemini_key": bool((os.getenv("GEMINI_API_KEY") or "").strip()),
    }

    date_str = card.get("date", "")
    if date_str:
        try:
            event_day = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            today = datetime.now().date()
            report["fight_night_today"] = today in (event_day, event_day + timedelta(days=1))
        except ValueError:
            pass

    if report["event_url"]:
        try:
            from modules import _13_live_wire as lw
            results = lw.get_live_results()
            report["scrape_ok"] = True
            report["finished_fights"] = len(results)
        except Exception as e:
            report["scrape_error"] = str(e)[:120]

    return report


def main():
    print("\n" + "=" * 60)
    print("🩺 FightIQ Pipeline Healthcheck")
    print("=" * 60)

    lw = check_live_wire_readiness()
    if lw.get("fight_night_today"):
        print("   🔥 Fight night detected")

    backend = lw.get("twitter_backend", "none")
    if backend == "official":
        print("   ✅ Twitter: official API v2 (tweepy)")
    elif backend == "cookies":
        print("   ✅ Twitter: cookie/twikit (default)")
    else:
        print("   ❌ Twitter: no credentials (set X_API_* or twitter_cookies.json)")

    if lw.get("twitter_cookies") and backend != "official":
        print("   ✅ Twitter cookies file present")
    print(f"   {'✅' if lw.get('event_url') else '❌'} Event URL in 1_card.json")
    if lw.get("scrape_ok"):
        print(f"   ✅ Live Wire scrape: {lw.get('finished_fights', 0)} finished bout(s) on page")
    elif lw.get("scrape_error"):
        print(f"   ❌ Live Wire scrape failed: {lw['scrape_error']}")
    if not lw.get("gemini_key"):
        print("   ❌ GEMINI_API_KEY missing in .env")
    else:
        print("   ✅ GEMINI_API_KEY loaded from .env")

    issues = check_card_coverage()
    if issues.get("skipped"):
        print(f"   ℹ️  Skipped: {issues['reason']}")
        # Content-safety still matters in IDLE mode (duplicate/retired
        # spotlight content is exactly an IDLE-mode failure)
        safety = check_content_safety()
        idle_hits = 0
        if safety["duplicate_spotlight"]:
            idle_hits += 1
            print("   🚨 DUPLICATE SPOTLIGHT: today's content matches an earlier post")
        if safety["inactive_spotlight"]:
            idle_hits += 1
            print(f"   🚨 INACTIVE FIGHTER in spotlight queue: {safety['inactive_spotlight']}")
        if not idle_hits:
            print("   ✅ Content safety: no repeats, no retired picks")
        print("=" * 60 + "\n")
        base_ok = lw.get("gemini_key") and lw.get("twitter_ready")
        return (0 if base_ok else 1) + 2 * min(1, idle_hits)

    total = issues["fights_total"]
    coverage = {
        "Deep stats":   total - len(issues["missing_deep_stats"]),
        "Odds":         total - len(issues["missing_odds"]),
        "AI brain":     total - len(issues["missing_ai_brain"]),
        "Versus cards": total - len(issues["missing_versus_cards"]),
    }
    print(f"   Fights tracked: {total}")
    for label, ok in coverage.items():
        icon = "✅" if ok == total else ("⚠️ " if ok > 0 else "❌")
        print(f"   {icon} {label}: {ok}/{total}")

    missing_imgs = issues["missing_portraits"]
    if missing_imgs:
        print(f"   ⚠️  Missing portraits: {len(missing_imgs)} — {missing_imgs[:5]}")
    else:
        print("   ✅ All fighter portraits cached")

    for key in ("missing_deep_stats", "missing_odds", "missing_ai_brain", "missing_versus_cards"):
        if issues[key]:
            print(f"   📋 {key}: {issues[key]}")

    # ── Content-safety guard layer (invented odds / repeats / retired picks) ──
    safety = check_content_safety()
    safety_hits = 0
    if safety["unsourced_odds"]:
        safety_hits += 1
        print(f"   🚨 UNSOURCED ODDS (possible invented prices): "
              f"{len(safety['unsourced_odds'])} — {safety['unsourced_odds'][:4]}")
    if safety["duplicate_spotlight"]:
        safety_hits += 1
        print("   🚨 DUPLICATE SPOTLIGHT: today's content matches an earlier post")
    if safety["inactive_spotlight"]:
        safety_hits += 1
        print(f"   🚨 INACTIVE FIGHTER in spotlight queue: {safety['inactive_spotlight']}")
    if not safety_hits:
        print("   ✅ Content safety: odds sourced, no repeats, no retired picks")
    issues["content_safety"] = safety

    snapshot_path = get_data_path("healthcheck.json")
    try:
        with open(snapshot_path, "w") as f:
            json.dump(issues, f, indent=2)
        print(f"   📁 Snapshot: {snapshot_path}")
    except Exception:
        pass

    print("=" * 60 + "\n")

    severity = sum(1 for k in ("missing_odds", "missing_ai_brain") if issues[k])
    if not lw.get("gemini_key") or not lw.get("twitter_ready"):
        severity += 1
    # Content-safety findings push severity to the Discord-alert threshold
    severity += 2 * min(1, safety_hits)
    return severity


if __name__ == "__main__":
    sys.exit(main())
