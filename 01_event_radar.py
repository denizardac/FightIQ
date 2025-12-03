import json
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

def main():
    print("--- STEP 1: FINDING EVENT (FREE MODE) ---")
    ua = UserAgent()
    url = "http://ufcstats.com/statistics/events/upcoming"
    
    headers = {'User-Agent': ua.random}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        event_row = soup.find('tr', class_='b-statistics__table-row_type_event')
        if not event_row:
            # Bazen tablo yapısı değişebilir, alternatif
            event_link_tag = soup.select_one("td.b-statistics__table-col a")
        else:
            event_link_tag = event_row.find('a')
            
        if not event_link_tag:
            print("❌ Could not find event link.")
            return

        event_name = event_link_tag.text.strip()
        event_url = event_link_tag['href']
        
        print(f"🏆 Target: {event_name}")
        print(f"📋 Fetching Card: {event_url}")
        
        card_response = requests.get(event_url, headers={'User-Agent': ua.random})
        card_soup = BeautifulSoup(card_response.text, 'html.parser')
        
        fights = []
        rows = card_soup.find_all('tr', class_='b-fight-details__table-row')
        
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue
            names = cols[1].find_all('a')
            if len(names) >= 2:
                fights.append({
                    "f1": names[0].text.strip(),
                    "f2": names[1].text.strip()
                })
        
        output = {"event": event_name, "fights": fights}
        with open("1_card.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4)
            
        print(f"✅ Saved {len(fights)} fights to '1_card.json'")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()