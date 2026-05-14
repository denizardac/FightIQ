"""
Debug Script: BestFightOdds Event Detail Page Structure
=========================================================
Tests access to BFO event detail pages to confirm prop bet availability.

Usage:
    python tests/debug_bfo_detail_page.py
"""

import requests
from bs4 import BeautifulSoup
import re

BESTFIGHTODDS_BASE = "https://www.bestfightodds.com"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_homepage():
    """Fetch homepage to find an active UFC event link"""
    print("=" * 70)
    print("STEP 1: Fetching BestFightOdds Homepage")
    print("=" * 70)
    
    try:
        resp = requests.get(BESTFIGHTODDS_BASE, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find UFC event links (e.g., /events/ufc-324-3456)
        event_links = soup.find_all('a', href=re.compile(r'/events/ufc'))
        
        if event_links:
            print(f"✅ Found {len(event_links)} UFC event links")
            # Get the first unique event link
            unique_links = set()
            for link in event_links:
                href = link.get('href')
                if href:
                    unique_links.add(href)
            
            if unique_links:
                first_event = list(unique_links)[0]
                print(f"📌 Testing event: {first_event}")
                return first_event
        else:
            print("❌ No UFC event links found on homepage")
            print("\nSearching for any event-related structure...")
            
            # Debug: print sample HTML structure
            tables = soup.find_all('table')
            print(f"Found {len(tables)} tables on page")
            
            rows = soup.find_all('tr')
            print(f"Found {len(rows)} table rows")
            
            # Look for fighter links
            fighter_links = soup.find_all('a', href=re.compile(r'/fighters/'))
            print(f"Found {len(fighter_links)} fighter links")
            
            if fighter_links:
                print("\nSample fighter links:")
                for i, link in enumerate(fighter_links[:5]):
                    print(f"  {i+1}. {link.get_text(strip=True)} -> {link.get('href')}")
            
            return None
            
    except Exception as e:
        print(f"❌ Error fetching homepage: {e}")
        return None


def fetch_event_detail(event_url):
    """Fetch specific event detail page"""
    print("\n" + "=" * 70)
    print(f"STEP 2: Fetching Event Detail Page")
    print("=" * 70)
    
    full_url = BESTFIGHTODDS_BASE + event_url
    print(f"URL: {full_url}")
    
    try:
        resp = requests.get(full_url, headers=HEADERS, timeout=15)
        print(f"✅ Response Status: {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Analyze page structure
        print("\n" + "-" * 70)
        print("PAGE STRUCTURE ANALYSIS")
        print("-" * 70)
        
        # Look for prop sections
        prop_indicators = [
            ('div', 'id', 'props'),
            ('div', 'id', 'div_props'),
            ('div', 'class', 'props'),
            ('table', 'class', 'props'),
            ('h2', 'text', 'props'),
            ('h3', 'text', 'method of victory'),
            ('span', 'text', 'method of victory'),
        ]
        
        print("\n1. Searching for Prop Bet Sections:")
        found_props = False
        for tag, attr_type, value in prop_indicators:
            if attr_type == 'id':
                elements = soup.find_all(tag, id=re.compile(value, re.I))
            elif attr_type == 'class':
                elements = soup.find_all(tag, class_=re.compile(value, re.I))
            else:  # text
                elements = soup.find_all(tag, string=re.compile(value, re.I))
            
            if elements:
                print(f"   ✅ Found {len(elements)} <{tag}> with {attr_type}={value}")
                found_props = True
                
                # Print sample content
                for elem in elements[:2]:
                    print(f"      Sample: {str(elem)[:150]}...")
        
        if not found_props:
            print("   ⚠️ No explicit prop sections found")
        
        # Look for bookmaker names
        print("\n2. Searching for Bookmaker Names:")
        bookmakers = ['DraftKings', 'FanDuel', 'BetMGM', 'Caesars', 'BetRivers']
        for book in bookmakers:
            if book.lower() in resp.text.lower():
                print(f"   ✅ Found: {book}")
        
        # Look for line movement section
        print("\n3. Searching for Line Movement Section:")
        movement_indicators = [
            soup.find(id=re.compile(r'linemovement', re.I)),
            soup.find(class_=re.compile(r'line.?movement', re.I)),
            soup.find(string=re.compile(r'since opening', re.I)),
            soup.find(string=re.compile(r'last 24 hours', re.I)),
        ]
        
        for indicator in movement_indicators:
            if indicator:
                print(f"   ✅ Found line movement indicator: {type(indicator).__name__}")
                # Get parent container
                if hasattr(indicator, 'parent'):
                    parent = indicator.parent
                    print(f"      Parent: {parent.name} {parent.get('class', [])} {parent.get('id', '')}")
        
        # Search for percentage patterns in text
        print("\n4. Searching for Percentage Patterns (e.g., +152%, -66%):")
        percentage_pattern = r'([+-]\d+%)'
        percentages = re.findall(percentage_pattern, resp.text)
        if percentages:
            unique_percentages = set(percentages)
            print(f"   ✅ Found {len(unique_percentages)} unique percentage values")
            print(f"      Samples: {list(unique_percentages)[:10]}")
        else:
            print("   ⚠️ No percentage patterns found")
        
        # Full HTML dump (first 5000 chars)
        print("\n" + "=" * 70)
        print("RAW HTML SAMPLE (First 5000 characters)")
        print("=" * 70)
        print(resp.text[:5000])
        print("\n[... truncated ...]")
        
        return soup
        
    except Exception as e:
        print(f"❌ Error fetching event detail: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("\n" + "🔍" * 35)
    print("BestFightOdds Event Detail Page - Debug Script")
    print("🔍" * 35 + "\n")
    
    # Step 1: Get event link from homepage
    event_url = fetch_homepage()
    
    if not event_url:
        print("\n❌ FAILED: Could not find event URL from homepage")
        print("💡 Trying manual fallback URL...")
        
        # Fallback: try a known UFC event structure
        event_url = "/events/ufc-324"
        print(f"Using fallback: {event_url}")
    
    # Step 2: Fetch event detail page
    soup = fetch_event_detail(event_url)
    
    if soup:
        print("\n" + "=" * 70)
        print("✅ DEBUG SCRIPT COMPLETE")
        print("=" * 70)
        print("Next Steps:")
        print("  1. Review the HTML structure above")
        print("  2. Identify exact selectors for props and line movement")
        print("  3. Update _03_odds_hunter.py with proper scraping logic")
    else:
        print("\n❌ DEBUG SCRIPT FAILED")


if __name__ == "__main__":
    main()
