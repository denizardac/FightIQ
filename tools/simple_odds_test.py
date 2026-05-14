# Simple Odds Source Test
import requests

sources = {
    "BestFightOdds": "https://www.bestfightodds.com",
    "MMAMania": "https://www.mmamania.com/odds"
}

for name, url in sources.items():
    try:
        r = requests.get(url, timeout=10)
        has_ufc = "ufc" in r.text.lower()
        print(f"{name}: Status={r.status_code}, UFC={has_ufc}, Size={len(r.text)} bytes")
        if has_ufc:
            print(f"  -> SCRAPABLE")
    except Exception as e:
        print(f"{name}: FAILED - {e}")
