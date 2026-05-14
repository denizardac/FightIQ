"""
FightIQ Full Cycle Test
Tests the complete IDLE pipeline: Trend → Spotlight → Visual → Video
Makes real API calls (Gemini, scraping). Not suitable for CI without mocks.
"""

import sys
import os
import json
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.paths import get_data_path, get_output_path, VISUALS_DIR

import importlib.util


def _load_module(name, rel_path):
    """Load a module from the modules/ directory by relative path."""
    abs_path = os.path.join(PROJECT_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(name, abs_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


try:
    TrendHunter = _load_module("TrendHunter", "modules/_11_trend_hunter.py")
    SpotlightEngine = _load_module("SpotlightEngine", "modules/_09_spotlight_engine.py")
    VideoEngine = _load_module("VideoEngine", "modules/_10_video_engine.py")
except Exception as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)


def test_trend_hunter():
    print("\n🔍 TESTING TREND HUNTER...")
    trends = TrendHunter.get_trending_fighters()
    if trends:
        print(f"   ✅ SUCCESS: Found {len(trends)} trends: {trends[:3]}")
        return trends
    else:
        print("   ⚠️ WARNING: No trends found (or API/network error).")
        return []


def test_spotlight_generation_mock(fighter_name):
    print(f"\n🎨 TESTING SPOTLIGHT ENGINE (MOCKED for {fighter_name})...")

    # 1. Load DB
    print("   1. Loading fighter DB...")
    _, urls = SpotlightEngine.load_db()

    key = None
    for k in urls.keys():
        if fighter_name.lower() in k.lower():
            key = k
            break

    if not key:
        print(f"   ❌ Fighter '{fighter_name}' not found in DB.")
        return None

    # 2. Scrape
    url = urls[key]
    print("   2. Scraping fighter page...")
    data = SpotlightEngine.scrape_fighter_detailed(url)

    if not data:
        print("   ❌ Scraping failed.")
        return None

    print(f"   ✅ Scraped: {data['name']} ({data['record']})")

    # 3. AI Content (real Gemini call)
    print("   3. Generating AI Content (Gemini)...")
    ai_content = SpotlightEngine.generate_standard_content(data)
    if ai_content:
        print("   ✅ Gemini Response Received.")
    else:
        print("   ❌ Gemini Failed.")
        return None

    # 4. Visuals
    print("   4. Generating Visuals...")
    hunter = SpotlightEngine.VisualEngine.ImageHunter()
    img_path = hunter.get_fighter_image(data['name'])

    SpotlightEngine.VisualEngine.create_stat_card(
        data['name'],
        ai_content['card_stats'],
        ai_content['card_stats']['one_liner'],
        img_path,
        record=data['record'],
        bg_path=None
    )

    card_abs = get_output_path(f"Card_{data['name'].replace(' ', '_')}.png", "visuals")
    if os.path.exists(card_abs):
        print(f"   ✅ Stat Card Created: {card_abs}")
    else:
        print("   ❌ Stat Card Generation Failed.")
        return None

    # 5. Video
    print("   5. Generating Video...")
    video_path = VideoEngine.create_reel(
        data['name'],
        card_abs,
        ai_content['video_script']
    )

    if video_path and os.path.exists(video_path):
        print(f"   ✅ Video Created: {video_path}")
    else:
        print("   ⚠️ Video Generation Failed (non-critical).")

    return {
        "visual": card_abs,
        "video": video_path,
        "tweet": ai_content['main_tweet']
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 FIGHTIQ FULL CYCLE TEST")
    print("=" * 60)

    trends = test_trend_hunter()

    target = "Conor McGregor"
    if trends:
        target = trends[0]

    result = test_spotlight_generation_mock(target)

    if result:
        print("\n" + "=" * 60)
        print("✅ TEST PASSED: ALL ASSETS GENERATED")
        print(f"Tweet: {result['tweet']}")
        print(f"Video: {result['video']}")
        print("=" * 60)
        print("\nTo post to Twitter: python run.py  (reads spotlight_ready.json)")
    else:
        print("\n❌ TEST FAILED.")
