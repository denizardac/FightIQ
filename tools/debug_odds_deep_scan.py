"""
DEEP DEBUG: BestFightOdds Scraper Analysis
Diagnoses why odds scraping is failing
"""

import requests
from bs4 import BeautifulSoup
import json
import difflib
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

print("="*80)
print("BESTFIGHTODDS.COM - DEEP DEBUG SCAN")
print("="*80)

# Load our fighter data
card_file = get_data_path("1_card.json")
our_fighters = []
if os.path.exists(card_file):
    with open(card_file, 'r', encoding='utf-8') as f:
        card_data = json.load(f)
        if card_data.get('fights'):
            for fight in card_data['fights']:
                our_fighters.extend(fight.get('fighters', []))
    print(f"\n[LOADED] Our card has {len(our_fighters)} fighters")
    print(f"Sample: {our_fighters[:3]}")
else:
    print("\n[WARNING] No 1_card.json found - using test fighters")
    our_fighters = ["Umar Nurmagomedov", "Deiveson Figueiredo", "Sean O'Malley"]

print("\n" + "="*80)
print("STEP 1: FETCHING BESTFIGHTODDS.COM")
print("="*80)

url = "https://www.bestfightodds.com"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

try:
    resp = requests.get(url, headers=headers, timeout=15)
    print(f"✅ HTTP Status: {resp.status_code}")
    print(f"✅ Content Length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    print("\n" + "="*80)
    print("STEP 2: FINDING ALL EVENT HEADERS")
    print("="*80)
    
    # Try multiple header strategies
    all_headers = []
    
    # Strategy 1: Look for h1, h2, h3
    for tag in ['h1', 'h2', 'h3', 'h4']:
        headers_found = soup.find_all(tag)
        for h in headers_found:
            text = h.get_text(strip=True)
            if text and len(text) > 3:
                all_headers.append((tag, text))
    
    print(f"\n[FOUND] {len(all_headers)} headers total")
    
    # Filter for UFC
    ufc_headers = [(tag, text) for tag, text in all_headers if 'UFC' in text.upper() or 'MMA' in text.upper()]
    
    print(f"[FILTERED] {len(ufc_headers)} UFC/MMA headers:")
    for tag, text in ufc_headers[:20]:  # Show first 20
        print(f"  <{tag}>: {text}")
    
    print("\n" + "="*80)
    print("STEP 3: EXTRACTING FIGHTER NAMES")
    print("="*80)
    
    # Strategy: Find all links that might be fighters
    fighter_links = soup.find_all('a', href=lambda h: h and ('/fighters/' in h or '/events/' in h))
    
    print(f"\n[FOUND] {len(fighter_links)} potential fighter/event links")
    
    # Extract unique fighter names
    fighters_on_site = set()
    for link in fighter_links:
        text = link.get_text(strip=True)
        if text and len(text) > 3 and not text.isdigit():
            fighters_on_site.add(text)
    
    fighters_on_site = list(fighters_on_site)
    print(f"[EXTRACTED] {len(fighters_on_site)} unique names")
    print(f"\nSample fighters on site:")
    for f in fighters_on_site[:15]:
        print(f"  - {f}")
    
    print("\n" + "="*80)
    print("STEP 4: FUZZY MATCHING TEST")
    print("="*80)
    
    print(f"\nTesting fuzzy match for our fighters against site data...")
    
    for our_fighter in our_fighters[:5]:  # Test first 5
        print(f"\n🔍 Searching for: '{our_fighter}'")
        
        # Get best matches
        matches = difflib.get_close_matches(our_fighter, fighters_on_site, n=3, cutoff=0.6)
        
        if matches:
            print(f"   ✅ MATCHES FOUND:")
            for match in matches:
                ratio = difflib.SequenceMatcher(None, our_fighter.lower(), match.lower()).ratio()
                print(f"      - '{match}' (Score: {ratio:.2f})")
        else:
            print(f"   ❌ NO MATCHES (trying lower cutoff...)")
            # Try with very low cutoff
            matches_low = difflib.get_close_matches(our_fighter, fighters_on_site, n=3, cutoff=0.4)
            if matches_low:
                print(f"   ⚠️ LOW-CONFIDENCE MATCHES:")
                for match in matches_low:
                    ratio = difflib.SequenceMatcher(None, our_fighter.lower(), match.lower()).ratio()
                    print(f"      - '{match}' (Score: {ratio:.2f})")
            else:
                print(f"   ❌ ABSOLUTELY NO MATCHES FOUND")
    
    print("\n" + "="*80)
    print("STEP 5: LOOKING FOR ODDS VALUES")
    print("="*80)
    
    # Find any text that looks like odds
    import re
    odds_pattern = re.compile(r'[+-]\d{2,4}')
    
    text_content = soup.get_text()
    odds_found = odds_pattern.findall(text_content)
    
    print(f"\n[FOUND] {len(odds_found)} values that look like American odds:")
    print(f"Sample: {odds_found[:20]}")
    
    # Try to find decimal odds too
    decimal_pattern = re.compile(r'\b[12]\.\d{2}\b')
    decimals_found = decimal_pattern.findall(text_content)
    
    print(f"\n[FOUND] {len(decimals_found)} values that look like decimal odds:")
    print(f"Sample: {decimals_found[:20]}")
    
    print("\n" + "="*80)
    print("STEP 6: HTML STRUCTURE ANALYSIS")
    print("="*80)
    
    # Look for table structures
    tables = soup.find_all('table')
    print(f"\n[FOUND] {len(tables)} tables on page")
    
    # Look for divs with class containing 'fight', 'match', 'event', 'odds'
    keywords = ['fight', 'match', 'event', 'odds', 'line', 'bet']
    relevant_divs = []
    
    for div in soup.find_all('div'):
        class_str = ' '.join(div.get('class', [])).lower()
        if any(kw in class_str for kw in keywords):
            relevant_divs.append(div)
    
    print(f"[FOUND] {len(relevant_divs)} divs with relevant classes")
    
    if relevant_divs:
        print(f"\nSample div classes:")
        for div in relevant_divs[:10]:
            classes = div.get('class', [])
            print(f"  - {classes}")
    
    print("\n" + "="*80)
    print("STEP 7: TARGET EVENT SEARCH (UFC 324)")
    print("="*80)
    
    # Search specifically for UFC 324
    ufc324_mentions = []
    for text_elem in soup.find_all(string=lambda s: s and '324' in str(s)):
        parent = text_elem.find_parent()
        if parent:
            ufc324_mentions.append({
                'tag': parent.name,
                'text': text_elem.strip()[:100],
                'class': parent.get('class', [])
            })
    
    print(f"\n[FOUND] {len(ufc324_mentions)} mentions of '324':")
    for mention in ufc324_mentions[:10]:
        print(f"  <{mention['tag']}> class={mention['class']}: {mention['text']}")
    
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    
    print(f"\n✅ Site is accessible: HTTP {resp.status_code}")
    print(f"✅ UFC headers found: {len(ufc_headers)}")
    print(f"✅ Fighter names extracted: {len(fighters_on_site)}")
    print(f"✅ Odds values present: {len(odds_found) + len(decimals_found)}")
    
    if len(ufc_headers) > 0 and len(fighters_on_site) > 0:
        print(f"\n🎯 VERDICT: Site has UFC data - scraper logic needs fixing")
    else:
        print(f"\n⚠️ VERDICT: Data structure may have changed - need new parsing strategy")
    
    print("\n" + "="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
