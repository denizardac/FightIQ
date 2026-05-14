"""
Betist Live Domain Scanner
Finds active Betist domain and tests data extraction
"""

import requests
from bs4 import BeautifulSoup
import re

print("="*70)
print("BETIST DOMAIN SCANNER")
print("="*70)

# Test known redirect
redirect_url = "https://cutt.ly/zrIT6E9d"

print(f"\n[1] Testing redirect URL: {redirect_url}")

try:
    resp = requests.get(redirect_url, allow_redirects=True, timeout=15, verify=False)
    final_url = resp.url
    domain = re.search(r'https?://([^/]+)', final_url).group(1) if final_url else None
    
    print(f"    Final URL: {final_url}")
    print(f"    Domain: {domain}")
    print(f"    Status: {resp.status_code}")
    
    if resp.status_code == 200 and domain:
        print(f"\n[2] Testing Betist API on {domain}")
        
        # Try to find UFC league
        base = f"https://{domain}"
        
        # Test league search
        test_ids = [74, 75, 76, 77, 164, 165, 166]
        
        for league_id in test_ids:
            try:
                params = {
                    'sec': 'ASIAN_LAYOUT',
                    'subsec': 'REQUEST_GET_SCHEME_EVENTS',
                    'league_id[]': league_id
                }
                
                r = requests.get(base, params=params, timeout=10, verify=False)
                if 'UFC' in r.text.upper():
                    print(f"    ✓ League ID {league_id}: FOUND UFC")
                    
                    soup = BeautifulSoup(r.text, 'html.parser')
                    rows = soup.find_all('tbody', class_='cont_odds_row')
                    print(f"      Fights found: {len(rows)}")
                    
                    if rows:
                        # Sample first fight
                        first = rows[0]
                        name_span = first.find('span', class_='not_favorite_part')
                        if name_span:
                            print(f"      Sample: {name_span.get_text(strip=True)}")
                            
                        # Try to extract event ID
                        onclick = first.find('td', class_='m-bet-grid__cell_count')
                        if onclick:
                            event_match = re.search(r'(\d+)', onclick.get('onclick', ''))
                            if event_match:
                                event_id = event_match.group(1)
                                print(f"      Event ID: {event_id}")
                                
                                # Test market detail
                                market_params = {
                                    'sec': 'ASIAN_LAYOUT',
                                    'subsec': 'REQUEST_GET_EVENT_MARKETS',
                                    'event_id': event_id
                                }
                                
                                mr = requests.get(base, params=market_params, timeout=10, verify=False)
                                msoup = BeautifulSoup(mr.text, 'html.parser')
                                
                                markets = msoup.find_all('div', class_='market-wrap-content')
                                print(f"      Markets found: {len(markets)}")
                                
                                for m in markets[:3]:
                                    mname = m.find('div', class_='market-name')
                                    if mname:
                                        print(f"        - {mname.get_text(strip=True)}")
                    
                    break
                    
            except Exception as e:
                continue
        
    else:
        print(f"\n❌ Redirect failed or blocked")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
