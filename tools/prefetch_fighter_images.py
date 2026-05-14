"""
Pre-fetch all fighter portraits for the current event card.

Reads data/1_card.json, finds all fighter names, and runs the multi-source
ImageHunter on every one in parallel. Results land in assets/images_cache/
so subsequent visual generation is offline-fast.

Designed to be safely cron-able: idempotent (skips cached fighters),
won't crash on individual failures, prints a per-fighter status summary.

Usage:
    python3 -m tools.prefetch_fighter_images
"""
import os
import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.paths import get_data_path
from modules._06_visual_engine import ImageHunter, IMG_CACHE_DIR

MAX_WORKERS = 6


def collect_fighter_names():
    """Pull every unique fighter name from the current card."""
    card_path = get_data_path("1_card.json")
    if not os.path.exists(card_path):
        print(f"⚠️  No card found at {card_path}")
        return []

    with open(card_path) as f:
        card = json.load(f)

    names = set()
    fights = card.get("fights", []) or card.get("matchups", [])
    for fight in fights:
        # support multiple schemas
        if isinstance(fight, dict):
            if "fighter1" in fight and "fighter2" in fight:
                names.add(fight["fighter1"])
                names.add(fight["fighter2"])
            elif "matchup" in fight and " vs " in fight["matchup"]:
                a, b = fight["matchup"].split(" vs ", 1)
                names.add(a.strip())
                names.add(b.strip())
            elif "fighters" in fight and isinstance(fight["fighters"], list):
                for n in fight["fighters"]:
                    if n:
                        names.add(n.strip())
    return sorted(n for n in names if n)


def hunt(name, hunter):
    safe = name.replace(" ", "_").lower()
    target = os.path.join(IMG_CACHE_DIR, f"{safe}.png")
    if os.path.exists(target):
        return name, "cached", target
    result = hunter.get_fighter_image(name)
    if result:
        return name, "fetched", result
    return name, "missing", None


def main():
    names = collect_fighter_names()
    if not names:
        print("No fighters found in card — nothing to prefetch.")
        return

    print(f"🎯 Pre-fetching portraits for {len(names)} fighters...\n")
    hunter = ImageHunter()

    summary = {"cached": 0, "fetched": 0, "missing": 0}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(hunt, n, hunter): n for n in names}
        for fut in as_completed(futures):
            name, status, _path = fut.result()
            summary[status] += 1
            icon = {"cached": "📁", "fetched": "🆕", "missing": "❌"}[status]
            print(f"  {icon} {name}: {status}")

    print("\n" + "=" * 50)
    print(f"📊 Summary: {summary['cached']} cached, "
          f"{summary['fetched']} freshly fetched, "
          f"{summary['missing']} missing (silhouette fallback)")
    print("=" * 50)


if __name__ == "__main__":
    main()
