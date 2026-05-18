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

from dotenv import load_dotenv

# Always load .env from project root (cron cwd may be /root)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from core.paths import get_data_path, VISUALS_DIR, ASSETS_DIR, PROJECT_ROOT
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

        safe_f1 = "".join(c for c in fight.get("f1", "") if c.isalnum() or c == " ").replace(" ", "_")
        safe_f2 = "".join(c for c in fight.get("f2", "") if c.isalnum() or c == " ").replace(" ", "_")
        card_paths = [
            os.path.join(VISUALS_DIR, f"Versus_{safe_f1}_vs_{safe_f2}.png"),
            os.path.join(VISUALS_DIR, f"Versus_{safe_f2}_vs_{safe_f1}.png"),
        ]
        if not any(os.path.exists(p) for p in card_paths):
            issues["missing_versus_cards"].append(f"{fight.get('f1')} vs {fight.get('f2')}")

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
        print("=" * 60 + "\n")
        return 0 if lw.get("gemini_key") and lw.get("twitter_ready") else 1

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
    return severity


if __name__ == "__main__":
    sys.exit(main())
