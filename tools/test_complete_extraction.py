"""
Complete Line Movement and Betist Props Extractor
"""

import requests
from bs4 import BeautifulSoup
import re
import json

print("="*70)
print("TASK 1: LINE MOVEMENT EXTRACTION")
print("="*70)

url = "https://www.bestfightodds.com"
resp = requests.get(url, timeout=15)
soup = BeautifulSoup(resp.text, 'html.parser')

# Strategy 1: Find divs/sections with "movement" or "trending"
movement_data = []

# Look for all elements containing percentage changes
all_text = soup.find_all(string=re.compile(r'[+-]?\d+%'))
print(f"Found {len(all_text)} percentage mentions")

# Extract fighter names near percentages
for text_elem in all_text:
    parent = text_elem.find_parent()
    if parent:
        # Look for fighter link in same row/container
        links = parent.find_all('a', href=re.compile(r'/fighters/'))
        if links:
            fighter = links[0].get_text(strip=True)
            pct = re.search(r'([+-]?\d+)%', text_elem).group(0)
            movement_data.append({"fighter": fighter, "change": pct})
            print(f"  {fighter}: {pct}")

print(f"\nExtracted {len(movement_data)} line movements")

print("\n" + "="*70)
print("TASK 2: BETIST PROPS EXTRACTION")
print("="*70)

import sys
sys.path.append('c:/Users/Deniz/Desktop/Projects/FightIQ')
from modules._03_odds_hunter import BetistEngine

betist = BetistEngine()

if betist.resolve_current_domain():
    print(f"Domain: {betist.base_domain}")
    
    if betist.find_ufc_league_id():
        print(f"League ID: {betist.active_league_id}")
        
        if betist.fetch_event_list():
            print(f"Events indexed: {len(betist.fighter_to_id)}")
            
            # Test first fight
            if betist.fighter_to_id:
                fighter_name = list(betist.fighter_to_id.keys())[0]
                event_id = betist.fighter_to_id[fighter_name]
                
                print(f"\nTesting: {fighter_name} (Event ID: {event_id})")
                
                markets = betist.fetch_market_detail(event_id)
                
                print(f"\nMarkets found: {len(markets)}")
                for market_name, odds in list(markets.items())[:10]:
                    print(f"  - {market_name}")
                    
                # Check for props
                props_keywords = ['round', 'method', 'finish', 'decision', 'ko', 'submission']
                prop_markets = {k: v for k, v in markets.items() if any(kw in k.lower() for kw in props_keywords)}
                
                print(f"\nProp markets found: {len(prop_markets)}")
                for name in prop_markets.keys():
                    print(f"  ✓ {name}")

print("\n" + "="*70)
