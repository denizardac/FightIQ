import requests
import re
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the BetistEngine class
from importlib import import_module
odds_module = import_module('03_odds_hunter')
BetistEngine = odds_module.BetistEngine

REDIRECT_URL = "https://cutt.ly/zrIT6E9d" 

def test_connection():
    print("--- 🕵️‍♂️ LIVE ODDS DIAGNOSTIC ---")
    
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings()
    
    try:
        print("\n1️⃣ Creating BetistEngine instance...")
        engine = BetistEngine()
        
        print("\n2️⃣ Resolving current domain...")
        if not engine.resolve_current_domain():
            print("   ❌ Domain resolution failed")
            return
        
        print(f"   ✅ Domain resolved: {engine.base_domain}")
        print(f"   ✅ API URL: {engine.base_url}")
        
        print("\n3️⃣ Testing UFC League ID Discovery...")
        if not engine.find_ufc_league_id():
            print("   ❌ Could not find valid UFC League ID")
            print("   💡 This may be expected if no UFC events are currently scheduled")
            return
        
        print(f"   ✅ Active League ID: {engine.active_league_id}")
        
        print("\n4️⃣ Fetching event list...")
        engine.fetch_event_list()
        
        if len(engine.fighter_to_id) > 0:
            print(f"\n🎉 SUCCESS! Found {len(engine.fighter_to_id)} fighters")
            print("\n📋 Sample fighters:")
            for i, (fighter, event_id) in enumerate(list(engine.fighter_to_id.items())[:5]):
                print(f"   {i+1}. {fighter} (Event ID: {event_id})")
        else:
            print("\n⚠️ No fighters found")
            print("   This could mean:")
            print("   - No UFC events currently scheduled on the betting site")
            print("   - League ID is correct but no active fights")
            print("   - Site structure may have changed")
            
    except Exception as e:
        print(f"\n❌ Fatal Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
