import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
import sys
import os

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

# UTF-8 Encoding
try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

# ==========================================
# ⚙️ AYARLAR
# ==========================================
INPUT_FILE = get_data_path("2_data_with_odds.json")
OUTPUT_FILE = get_data_path("2_data_final.json")

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass


def _parse_official_record(soup):
    """UFCStats header record: 'Record: 22-3-0' or '22-3-0'. Returns (w,l,d) or None."""
    tag = soup.find("span", class_="b-content__title-record")
    if not tag:
        return None
    txt = tag.get_text(strip=True)
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", txt.replace("Record:", "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _result_from_td(td):
    """Return 'win'|'loss'|'draw'|'nc'|None(skip/next/unknown)."""
    if not td:
        return None
    txt = td.get_text(" ", strip=True).lower()
    if "next" in txt and len(txt) < 20:
        return None
    for flag in td.find_all("i"):
        cls = " ".join(flag.get("class") or [])
        cl = cls.lower()
        if "green" in cl or "b-flag_style_green" in cl:
            return "win"
        if "red" in cl or "b-flag_style_red" in cl:
            return "loss"
        if "gray" in cl and "draw" in txt:
            return "draw"
    if txt.startswith("w") and "loss" not in txt[:12]:
        return "win"
    if txt.startswith("l"):
        return "loss"
    if "draw" in txt or "d " in txt:
        return "draw"
    if "nc" in txt or "no contest" in txt:
        return "nc"
    return None


def _parse_method_round_time(cols):
    """
    UFCStats career rows vary in width; last cells are usually Round + Time.
    Returns (method_lower, round_str, time_str) or None if not a completed bout row.
    """
    texts = [c.get_text(" ", strip=True) for c in cols]
    n = len(texts)
    if n < 6:
        return None
    time_str = texts[-1]
    round_str = texts[-2]
    if not re.match(r"^\d{1,2}:\d{2}$", time_str):
        # Some rows use '--' for scheduled bouts
        if time_str in ("--", "", "N/A"):
            return None
        return None
    if not round_str.isdigit():
        return None
    # Method: prefer column before round (classic 10-col layout); else scan
    method_raw = texts[-3].lower() if n >= 3 else ""
    if len(method_raw) < 3:
        method_raw = " ".join(t.lower() for t in texts[1:-2] if t)
    return method_raw, round_str, time_str


class DeepStatsEngine:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch(self, url):
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.headers, timeout=18)
                if resp.status_code == 200:
                    return resp
                last_err = f"HTTP {resp.status_code}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {str(e)[:80]}"
                time.sleep(1.2 * (attempt + 1))
        print(f"      ⚠️ Fetch failed after retries: {last_err}")
        return None

    def time_to_seconds(self, time_str):
        try:
            if ":" not in time_str:
                return 0
            parts = time_str.split(":")
            if len(parts) != 2:
                return 0
            m, s = int(parts[0]), int(parts[1])
            return m * 60 + s
        except Exception:
            return 0

    def calculate_age(self, dob_str):
        """Calculate age with multiple date format support"""
        try:
            dob_str = " ".join(dob_str.split()).strip()
            if not dob_str or dob_str == "--":
                return "N/A"

            formats = ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d", "%b. %d, %Y", "%B. %d, %Y"]
            dob = None
            for fmt in formats:
                try:
                    dob = datetime.strptime(dob_str, fmt)
                    break
                except Exception:
                    continue

            if not dob:
                print(f"      ⚠️ Could not parse date: {dob_str}")
                return "N/A"

            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except Exception as e:
            print(f"      ⚠️ Age calculation error: {e}")
            return "N/A"

    def analyze_fighter_profile(self, url):
        if not url:
            return None

        resp = self._fetch(url)
        if not resp:
            return None

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            stats = {
                "name": "",
                "height": "N/A",
                "weight": "N/A",
                "reach": "N/A",
                "stance": "N/A",
                "age": "N/A",
                "total_fights": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "win_by_ko": 0,
                "win_by_sub": 0,
                "win_by_dec": 0,
                "first_round_finishes": 0,
                "avg_fight_time_sec": 0,
                "avg_fight_time": "0:00",
                "last_5_results": [],
            }

            name_tag = soup.find("span", class_="b-content__title-highlight")
            if name_tag:
                stats["name"] = name_tag.get_text(strip=True)

            rec_hdr = _parse_official_record(soup)
            if rec_hdr:
                stats["wins"], stats["losses"], stats["draws"] = rec_hdr

            for item in soup.find_all("li", class_=re.compile(r"b-list__box-list-item")):
                text = " ".join(item.get_text().split())
                if "Height:" in text:
                    stats["height"] = text.split("Height:", 1)[1].strip()
                elif "Weight:" in text:
                    stats["weight"] = text.split("Weight:", 1)[1].strip()
                elif "Reach:" in text:
                    stats["reach"] = text.replace("Reach:", "").strip()
                elif "stance:" in text.lower():
                    stats["stance"] = text.split(":", 1)[-1].strip() if ":" in text else stats["stance"]
                elif "DOB:" in text:
                    stats["age"] = self.calculate_age(text.replace("DOB:", "").strip())

            rows = soup.find_all("tr", class_="b-fight-details__table-row")
            total_seconds_fought = 0
            fight_count_for_time = 0

            table_wins = table_losses = 0
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 6:
                    continue
                hdr = cols[0].get_text(strip=True).upper()
                if hdr == "W/L" or "BOUT" in hdr:
                    continue

                outcome = _result_from_td(cols[0])
                if outcome is None:
                    continue

                mrt = _parse_method_round_time(cols)
                if not mrt:
                    continue
                method_raw, round_num, time_str = mrt

                stats["total_fights"] += 1
                if len(stats["last_5_results"]) < 5:
                    stats["last_5_results"].append(outcome)

                if outcome == "win":
                    table_wins += 1
                    if "ko" in method_raw or "tko" in method_raw:
                        stats["win_by_ko"] += 1
                    elif any(
                        t in method_raw
                        for t in ("sub", "choke", "armbar", "kimura", "guillotine", "triangle", "rear-naked")
                    ):
                        stats["win_by_sub"] += 1
                    elif "dec" in method_raw:
                        stats["win_by_dec"] += 1
                    if round_num == "1" and (
                        "ko" in method_raw or "tko" in method_raw or "sub" in method_raw or "choke" in method_raw
                    ):
                        stats["first_round_finishes"] += 1
                elif outcome == "loss":
                    table_losses += 1

                r = int(round_num)
                t_sec = self.time_to_seconds(time_str)
                total_seconds_fought += (r - 1) * 300 + t_sec
                fight_count_for_time += 1

            # If header record missing, fall back to table counts (+ draws unknown)
            if rec_hdr is None:
                stats["wins"] = table_wins
                stats["losses"] = table_losses

            if stats["wins"] > 0 or table_wins > 0:
                denom = stats["wins"] if stats["wins"] else table_wins
                stats["ko_rate"] = round((stats["win_by_ko"] / denom) * 100, 1) if denom else 0
                stats["sub_rate"] = round((stats["win_by_sub"] / denom) * 100, 1) if denom else 0
                stats["dec_rate"] = round((stats["win_by_dec"] / denom) * 100, 1) if denom else 0
            else:
                stats["ko_rate"] = stats["sub_rate"] = stats["dec_rate"] = 0

            if fight_count_for_time > 0:
                avg_sec = total_seconds_fought / fight_count_for_time
                m = int(avg_sec // 60)
                s = int(avg_sec % 60)
                stats["avg_fight_time"] = f"{m}:{s:02d}"
                stats["avg_fight_time_sec"] = avg_sec
            else:
                stats["avg_fight_time"] = "N/A"

            return stats

        except Exception as e:
            print(f"      ⚠️ Profile parsing error: {e}")
            return None

def main():
    print("--- 🧬 STEP 4: DEEP STATS ENGINE (V2 FIXED) ---")
    
    # Robust file load with validation
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: '{INPUT_FILE}' not found. Run Step 3 (odds_hunter) first.")
        return
    
    # Check file age
    file_age = time.time() - os.path.getmtime(INPUT_FILE)
    if file_age > 24 * 3600:  # 24 hours
        print(f"⚠️ WARNING: {INPUT_FILE} is {file_age/3600:.1f} hours old. Data may be stale.")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: {INPUT_FILE} contains invalid JSON: {e}")
        return
    except Exception as e:
        print(f"❌ ERROR: Failed to load {INPUT_FILE}: {e}")
        return

    engine = DeepStatsEngine()
    
    for fight in data:
        f1_name, f2_name = fight['fighters']
        print(f"\n📊 Analyzing Deep Stats: {f1_name} vs {f2_name}")
        
        urls = fight.get('urls', [])
        if len(urls) < 2:
            print("   ❌ Missing URLs.")
            continue
            
        deep1 = engine.analyze_fighter_profile(urls[0]) if urls[0] else None
        deep2 = engine.analyze_fighter_profile(urls[1]) if len(urls) > 1 and urls[1] else None

        def default_deep(name):
            return {"name": name, "height": "N/A", "weight": "N/A", "reach": "N/A", "stance": "N/A", "age": "N/A",
                    "total_fights": 0, "wins": 0, "losses": 0, "draws": 0, "win_by_ko": 0,
                    "win_by_sub": 0, "win_by_dec": 0, "first_round_finishes": 0,
                    "avg_fight_time_sec": 0, "avg_fight_time": "N/A", "last_5_results": [],
                    "ko_rate": 0, "sub_rate": 0, "dec_rate": 0}

        if deep1 or deep2:
            d1 = deep1 if deep1 else default_deep(f1_name)
            d2 = deep2 if deep2 else default_deep(f2_name)
            fight['deep_stats'] = [d1, d2]
            if deep1:
                print(f"      ✅ {f1_name}: {d1['wins']} Wins (KO:{d1['win_by_ko']} SUB:{d1['win_by_sub']} DEC:{d1['win_by_dec']})")
            else:
                print(f"      ⚠️ {f1_name}: No UFC profile found — using defaults")
            if deep2:
                print(f"      ✅ {f2_name}: {d2['wins']} Wins (KO:{d2['win_by_ko']} SUB:{d2['win_by_sub']} DEC:{d2['win_by_dec']})")
            else:
                print(f"      ⚠️ {f2_name}: No UFC profile found — using defaults")
        else:
            print("      ⚠️ Failed to extract deep stats for both fighters.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n📁 Final Data Saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()