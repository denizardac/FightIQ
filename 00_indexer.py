import requests
from bs4 import BeautifulSoup
import json
import string
import time

def create_fighter_database():
    print("--- 📚 UFC FIGHTER DATABASE CREATOR ---")
    print("Indexing all fighters... This happens only ONCE.")
    
    base_url = "http://ufcstats.com/statistics/fighters?char={}&page=all"
    alphabet = string.ascii_lowercase 
    fighter_db = {}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    total_count = 0
    
    for char in alphabet:
        url = base_url.format(char)
        print(f"   📂 Indexing '{char.upper()}'...", end="")
        
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            rows = soup.find_all('tr', class_='b-statistics__table-row')
            
            count = 0
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 2: continue
                
                link_tag = cols[0].find('a')
                if not link_tag: continue
                
                # İsimleri temizle (First Last)
                first_name = link_tag.text.strip()
                last_name = cols[1].text.strip()
                full_name = f"{first_name} {last_name}"
                
                link = link_tag['href']
                
                # Veritabanına ekle: "conor mcgregor": "http://..."
                fighter_db[full_name.lower()] = link
                count += 1
                total_count += 1
            
            print(f" ✅ Found {count} fighters.")
            time.sleep(1) # Siteyi yormamak için bekleme
            
        except Exception as e:
            print(f" ❌ Error: {e}")

    # Kaydet
    with open("fighters_db.json", "w", encoding="utf-8") as f:
        json.dump(fighter_db, f, indent=4)
        
    print(f"\n🎉 Database Complete! Total Fighters: {total_count}")
    print("Saved to 'fighters_db.json'")

if __name__ == "__main__":
    create_fighter_database()