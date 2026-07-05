import json
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
import sys
import re
import os

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path
from core.pipeline_meta import stamp_stage
from core.ufcstats_http import fetch as ufcstats_fetch

# ==========================================
# ⚙️ AYARLAR
# ==========================================
OUTPUT_FILE = get_data_path("1_card.json")
# Maç haftası limiti (6 gün önceden başlar, Cumartesi 0. gün olur)
FIGHT_WEEK_LIMIT = 6 

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def parse_ufc_date(raw_text):
    try:
        # Metin temizliği (PimblettJanuary -> Pimblett January)
        clean_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_text)
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', clean_text, re.IGNORECASE)
        if match:
            return datetime.strptime(match.group(0), "%B %d, %Y")
        return None
    except Exception:
        return None

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _user_agent(ua_obj):
    """Return a UA string, falling back if fake_useragent is misconfigured."""
    try:
        return ua_obj.random
    except Exception:
        return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0 Safari/537.36")


def fetch_event(ua):
    url = "http://ufcstats.com/statistics/events/upcoming"
    print(f"   🌐 Checking: {url}")
    last_err = None
    for attempt in range(3):
        try:
            resp = ufcstats_fetch(url, headers={'User-Agent': _user_agent(ua)})
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')

            rows = soup.find_all('tr', class_='b-statistics__table-row')
            target_row = None
            for row in rows:
                if row.find('a'):
                    target_row = row
                    break
            if not target_row:
                last_err = "no event row"
                continue

            link = target_row.find('a')
            date_text = "Unknown"
            for col in target_row.find_all('td'):
                txt = col.get_text(strip=True)
                if any(m in txt for m in MONTH_NAMES):
                    date_text = txt
                    break

            return link.text.strip(), link['href'], date_text
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"
    print(f"   ❌ fetch_event failed after 3 attempts ({last_err})")
    return None

def _write_card(payload):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    print(f"   📁 Saved to '{OUTPUT_FILE}'")


def main():
    print("--- 📡 STEP 1: EVENT RADAR (CALENDAR SYNC) ---")
    ua = UserAgent()

    event_data = fetch_event(ua)
    if not event_data:
        # CRITICAL: never leave a stale card behind. Write an explicit ERROR
        # status so the orchestrator aborts instead of re-running FIGHT WEEK
        # against last week's card, and exit non-zero.
        print("   ❌ No events found — writing ERROR card and aborting.")
        _write_card({
            "event": "", "date": "", "status": "ERROR",
            "days_until": 999, "url": "", "fights": [],
            "error": "fetch_event failed (network or markup change)",
        })
        sys.exit(1)

    name, url, date_txt = event_data
    print(f"   🎯 Event: {name}")

    # Tarih Hesaplama
    event_date = parse_ufc_date(date_txt)
    status = "IDLE"
    days_diff = 999
    final_date = date_txt

    if event_date:
        # Takvim günü farkı (saat bileşeninden bağımsız — eski `+1` düzeltmesi
        # gece yarısı çevresinde LIVE/IDLE'ı yanlış seçebiliyordu)
        days_diff = (event_date.date() - datetime.now().date()).days
        final_date = event_date.strftime("%Y-%m-%d")
        print(f"   ⏳ Days Until Fight: {days_diff}")

        # --- KRİTİK MOD SEÇİMİ ---
        # 0 = Bugün Maç Var (Cumartesi)
        # 1-6 = Maç Haftası (Pazar'dan Cuma'ya kadar olan süreç)
        if 0 <= days_diff <= FIGHT_WEEK_LIMIT:
            print("   🔥 STATUS: FIGHT WEEK! (LIVE)")
            status = "LIVE"
        else:
            print("   ☕ STATUS: OFF-SEASON / BUILD-UP (IDLE)")
            status = "IDLE"

    # Kartı Çek (with retry)
    fights = []
    for attempt in range(3):
        try:
            c_resp = ufcstats_fetch(url, headers={'User-Agent': _user_agent(ua)})
            if c_resp.status_code != 200:
                continue
            c_soup = BeautifulSoup(c_resp.text, 'html.parser')
            for r in c_soup.find_all('tr', class_='b-fight-details__table-row'):
                cols = r.find_all('td')
                if len(cols) >= 2:
                    ns = cols[1].find_all('a')
                    if len(ns) >= 2:
                        fights.append({"f1": ns[0].text.strip(), "f2": ns[1].text.strip()})
            if fights:
                break
        except Exception as e:
            print(f"   ⚠️ Card fetch attempt {attempt+1} failed: {type(e).__name__}: {str(e)[:80]}")

    _write_card({
        "event": name, "date": final_date, "status": status,
        "days_until": days_diff, "url": url, "fights": fights
    })
    stamp_stage("1_card", name)

    if status == "LIVE" and not fights:
        # A LIVE card with zero fights would make the whole week's pipeline
        # silently produce nothing — surface it as a failure.
        print("   ❌ LIVE event but fight card could not be scraped — failing.")
        sys.exit(1)

if __name__ == "__main__":
    main()