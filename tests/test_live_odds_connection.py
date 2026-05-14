"""
FightIQ Live Odds Connection Test
Tests live connectivity to the Betist odds scraper.
Makes REAL HTTP requests — requires network access.
"""

import sys
import os
import urllib3

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from modules import _03_odds_hunter as odds_module

BetistEngine = odds_module.BetistEngine


def test_connection():
    print("--- 🕵️ LIVE ODDS DIAGNOSTIC ---")

    urllib3.disable_warnings()

    try:
        print("\n1. Creating BetistEngine instance...")
        engine = BetistEngine()

        print("\n2. Resolving current domain...")
        if not engine.resolve_current_domain():
            print("   ❌ Domain resolution failed")
            return
        print(f"   ✅ Domain resolved: {engine.base_domain}")
        print(f"   ✅ API URL: {engine.base_url}")

        print("\n3. Testing UFC League ID Discovery...")
        if not engine.find_ufc_league_id():
            print("   ❌ Could not find valid UFC League ID")
            print("   💡 Expected if no UFC events are currently scheduled on Betist")
            return
        print(f"   ✅ Active League ID: {engine.active_league_id}")

        print("\n4. Fetching event list...")
        engine.fetch_event_list()

        if len(engine.fighter_to_id) > 0:
            print(f"\n🎉 SUCCESS! Found {len(engine.fighter_to_id)} fighters")
            print("\n📋 Sample fighters:")
            for i, (fighter, event_id) in enumerate(list(engine.fighter_to_id.items())[:5]):
                print(f"   {i + 1}. {fighter} (Event ID: {event_id})")
        else:
            print("\n⚠️ No fighters found")
            print("   Possible causes:")
            print("   - No UFC events currently scheduled on the betting site")
            print("   - League ID correct but no active fights")
            print("   - Site structure may have changed")

    except Exception as e:
        print(f"\n❌ Fatal Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_connection()
