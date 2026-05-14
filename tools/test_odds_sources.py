"""
FightIQ Odds Sources Verification Script
Tests scrapability and accessibility of potential odds sources.
"""

import requests
from bs4 import BeautifulSoup
import time

# ==========================================
# TEST CONFIGURATION
# ==========================================

SOURCES = {
    "BestFightOdds": "https://www.bestfightodds.com",
    "FightOdds.io": "https://www.fightodds.io",
    "MMAMania": "https://www.mmamania.com/odds",
    "Tapology": "https://www.tapology.com/betodds/upcoming-ufc-events",
    "OddsChecker": "https://www.oddschecker.com/us/ufc-mma",
    "Bet365": "https://www.bet365.com",
    "DraftKings": "https://sportsbook.draftkings.com/leagues/mma/ufc"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# TEST FUNCTIONS
# ==========================================

def test_source(name, url):
    """Test a single odds source"""
    print(f"\n{'='*70}")
    print(f"🔍 TESTING: {name}")
    print(f"📍 URL: {url}")
    print(f"{'='*70}")
    
    try:
        # Make request
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        
        # Print status
        status_emoji = "✅" if resp.status_code == 200 else "❌"
        print(f"{status_emoji} HTTP Status: {resp.status_code}")
        print(f"📏 Content Length: {len(resp.text)} bytes")
        print(f"🔗 Final URL: {resp.url}")
        
        # Parse HTML
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for UFC/MMA indicators
        text = resp.text.lower()
        ufc_found = 'ufc' in text
        mma_found = 'mma' in text or 'mixed martial' in text
        odds_found = any(indicator in text for indicator in ['odds', 'betting', 'moneyline', 'decimal'])
        
        print(f"\n📊 CONTENT ANALYSIS:")
        print(f"   {'✅' if ufc_found else '❌'} Contains 'UFC': {ufc_found}")
        print(f"   {'✅' if mma_found else '❌'} Contains 'MMA': {mma_found}")
        print(f"   {'✅' if odds_found else '❌'} Contains odds keywords: {odds_found}")
        
        # Try to extract sample data
        print(f"\n🎯 SAMPLE EXTRACTION:")
        
        if name == "BestFightOdds":
            # Look for fighter links
            fighter_links = soup.find_all('a', href=lambda h: h and '/fighters/' in h)
            if fighter_links:
                print(f"   ✅ Found {len(fighter_links)} fighter links")
                print(f"   📋 Sample: {fighter_links[0].get_text(strip=True)}")
                
                # Try to find odds values
                odds_elements = soup.find_all(string=lambda s: s and any(c in str(s) for c in ['+', '-', '.']))
                numeric_odds = [o.strip() for o in odds_elements if o.strip() and len(o.strip()) < 10]
                if numeric_odds:
                    print(f"   ✅ Sample odds found: {numeric_odds[:5]}")
                else:
                    print(f"   ⚠️ No numeric odds extracted")
            else:
                print(f"   ❌ No fighter links found")
        
        elif name == "MMAMania":
            # Look for article titles
            articles = soup.find_all(['h2', 'h3', 'a'])
            ufc_articles = [a.get_text(strip=True) for a in articles if 'ufc' in a.get_text(strip=True).lower()]
            if ufc_articles:
                print(f"   ✅ Found {len(ufc_articles)} UFC-related elements")
                print(f"   📋 Sample: {ufc_articles[0][:100]}")
            else:
                print(f"   ⚠️ No UFC content found")
        
        # Print HTML snippet
        print(f"\n📄 HTML SNIPPET (first 500 chars):")
        print(f"{resp.text[:500]}")
        
        # Check for blocking indicators
        blocking_indicators = [
            'cloudflare', 'captcha', 'challenge', 'access denied',
            'forbidden', 'bot detection', 'security check'
        ]
        blocked = any(indicator in text for indicator in blocking_indicators)
        
        if blocked:
            print(f"\n⚠️ WARNING: Possible bot protection detected!")
            for indicator in blocking_indicators:
                if indicator in text:
                    print(f"   - Found: '{indicator}'")
        
        # Final verdict
        print(f"\n{'='*70}")
        if resp.status_code == 200 and (ufc_found or mma_found) and not blocked:
            print(f"✅ VERDICT: {name} appears SCRAPABLE")
        elif resp.status_code == 200 and blocked:
            print(f"⚠️ VERDICT: {name} is BLOCKED (bot protection)")
        elif resp.status_code in [403, 401]:
            print(f"❌ VERDICT: {name} is ACCESS DENIED")
        elif resp.status_code == 404:
            print(f"❌ VERDICT: {name} is NOT FOUND")
        else:
            print(f"⚠️ VERDICT: {name} status unclear (status {resp.status_code})")
        print(f"{'='*70}")
        
        return {
            "name": name,
            "status_code": resp.status_code,
            "scrapable": resp.status_code == 200 and (ufc_found or mma_found) and not blocked,
            "blocked": blocked,
            "has_ufc": ufc_found or mma_found
        }
        
    except requests.exceptions.Timeout:
        print(f"❌ ERROR: Request timeout (>15s)")
        return {"name": name, "status_code": 0, "scrapable": False, "error": "timeout"}
    except requests.exceptions.ConnectionError as e:
        print(f"❌ ERROR: Connection failed - {e}")
        return {"name": name, "status_code": 0, "scrapable": False, "error": "connection"}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"name": name, "status_code": 0, "scrapable": False, "error": str(e)}

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║         FIGHTIQ ODDS SOURCES VERIFICATION TEST                 ║
    ║                P0 CRITICAL: PROOF OF LIFE                      ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    results = []
    
    for name, url in SOURCES.items():
        result = test_source(name, url)
        results.append(result)
        time.sleep(2)  # Rate limiting
    
    # Final summary
    print(f"\n\n{'='*70}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'='*70}\n")
    
    scrapable = [r for r in results if r.get('scrapable')]
    blocked = [r for r in results if r.get('blocked')]
    failed = [r for r in results if not r.get('scrapable') and not r.get('blocked')]
    
    print(f"✅ SCRAPABLE SOURCES ({len(scrapable)}):")
    for r in scrapable:
        print(f"   - {r['name']} (HTTP {r['status_code']})")
    
    print(f"\n⚠️ BLOCKED SOURCES ({len(blocked)}):")
    for r in blocked:
        print(f"   - {r['name']} (HTTP {r.get('status_code', 'N/A')})")
    
    print(f"\n❌ FAILED SOURCES ({len(failed)}):")
    for r in failed:
        print(f"   - {r['name']} (HTTP {r.get('status_code', 'N/A')}) - {r.get('error', 'unknown')}")
    
    print(f"\n{'='*70}")
    print(f"🎯 RECOMMENDED PRIMARY SOURCE:")
    if scrapable:
        best = scrapable[0]
        print(f"   ✅ {best['name']}")
        print(f"   📍 HTTP {best['status_code']}")
        print(f"   🔓 No bot protection detected")
    else:
        print(f"   ❌ NO SCRAPABLE SOURCES FOUND!")
        print(f"   💡 Consider using a paid API or headless browser")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
