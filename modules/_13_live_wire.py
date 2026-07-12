import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

# ==========================================
# FIGHTIQ: LIVE WIRE (Real-Time Commentary)
# ==========================================

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, PROJECT_ROOT
from core.ufcstats_http import fetch as ufcstats_fetch

try:
    from modules import _08_social_director as SocialDirector
except ImportError:
    SocialDirector = None

try:
    import core.config as config
    POLL_INTERVAL = config.LIVE_WIRE_POLL_INTERVAL
    MAX_RUNTIME_HOURS = config.LIVE_WIRE_MAX_RUNTIME_HOURS
    GEMINI_MODELS = config.GEMINI_MODELS
except ImportError:
    POLL_INTERVAL = 60
    MAX_RUNTIME_HOURS = 8
    GEMINI_MODELS = ["models/gemini-2.5-flash"]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

CARD_FILE = get_data_path("1_card.json")
RESULTS_FILE = get_data_path("3_results.json")
LIVE_WIRE_HISTORY = get_data_path("live_wire_history.json")
PUBLISHED_PICKS_FILE = get_data_path("published_picks.json")
COOKIES_FILE = get_data_path("twitter_cookies.json")

UFC_STATS_COMPLETED = "http://ufcstats.com/statistics/events/completed"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    )
}


api_key = os.getenv("GEMINI_API_KEY")
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"⚠️ GenAI Client Init Error: {e}")


def load_card():
    if not os.path.exists(CARD_FILE):
        return {}
    try:
        with open(CARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_fight_night(card=None):
    """True when today's date matches the card event date (fight night)."""
    card = card or load_card()
    if not card:
        return False
    date_str = card.get("date", "")
    if not date_str:
        return False
    try:
        event_day = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    today = datetime.now().date()
    # Also allow day-after for cards that run past midnight UTC
    return today in (event_day, event_day + timedelta(days=1))


def load_history():
    if os.path.exists(LIVE_WIRE_HISTORY):
        try:
            with open(LIVE_WIRE_HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history):
    try:
        with open(LIVE_WIRE_HISTORY, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠️ Could not save live wire history: {e}")


def _event_url_from_card(card):
    url = (card or {}).get("url", "").strip()
    if url and "event-details" in url:
        return url
    return None


def _event_url_from_completed(expected_event=""):
    """Fallback: newest completed UFCStats event."""
    try:
        response = ufcstats_fetch(UFC_STATS_COMPLETED, headers=REQUEST_HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        for row in soup.find_all("tr", class_="b-statistics__table-row"):
            link = row.find("a", class_="b-link") or row.find("a")
            if not link or not link.get("href"):
                continue
            name = link.text.strip()
            if expected_event:
                a = {w.lower() for w in name.split() if len(w) > 3}
                b = {w.lower() for w in expected_event.split() if len(w) > 3}
                if a and b and not (a & b):
                    continue
            return link["href"], name
    except Exception as e:
        print(f"   ⚠️ Completed events fetch failed: {e}")
    return None, None


def _parse_fight_row(row):
    """
    Parse one UFCStats event-details row.
    Current layout (2026): col0 = win flag, col1 = two fighters (winner first),
    col7 = method, col8 = round, col9 = time. Round/time let us settle
    Over/Under and distance bets honestly.
    """
    cols = row.find_all("td")
    if len(cols) < 8:
        return None

    flag_col = cols[0]
    flag_text = flag_col.get_text(" ", strip=True).lower()
    # Old code searched for a TAG named 'b-flag_style_green' (always None) —
    # the green flag is a class on an <i>/<a> element.
    green_flag = flag_col.find(class_=re.compile(r"b-flag_style_green"))
    has_win = bool(green_flag) or flag_text == "win"
    if not has_win:
        return None  # Fight not finished yet

    fighter_links = cols[1].find_all("a", class_="b-link")
    if len(fighter_links) < 2:
        return None

    winner = fighter_links[0].text.strip()
    loser = fighter_links[1].text.strip()

    method_parts = []
    for p in cols[7].find_all("p", class_="b-fight-details__table-text"):
        t = p.get_text(strip=True)
        if t:
            method_parts.append(t)
    method = " ".join(method_parts) if method_parts else "Decision"

    round_num, time_str = None, None
    if len(cols) >= 10:
        r_txt = cols[8].get_text(" ", strip=True)
        t_txt = cols[9].get_text(" ", strip=True)
        if r_txt.isdigit():
            round_num = int(r_txt)
        if re.match(r"^\d{1,2}:\d{2}$", t_txt):
            time_str = t_txt

    return {
        "winner": winner, "loser": loser, "method": method,
        "round": round_num, "time": time_str,
    }


# ==========================================
# PUBLISHED-PICK HONESTY LAYER
# The bot may only claim "we called it" for picks that were actually
# TWEETED (recorded in published_picks.json by the Social Director).
# Internal predictions that never reached Twitter are not claimable.
# ==========================================

def _norm_name(name):
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum() or ch == " ").strip()


def _names_match(a, b):
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    pa = [p for p in na.split() if len(p) > 2]
    pb = [p for p in nb.split() if len(p) > 2]
    return bool(pa and pb and pa[-1] == pb[-1])


def load_published_picks():
    if not os.path.exists(PUBLISHED_PICKS_FILE):
        return {}
    try:
        with open(PUBLISHED_PICKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def find_published_pick(published, winner, loser):
    for matchup, rec in published.items():
        if " vs " not in matchup:
            continue
        a, b = matchup.split(" vs ", 1)
        if (_names_match(winner, a) and _names_match(loser, b)) or \
           (_names_match(winner, b) and _names_match(loser, a)):
            return rec
    return None


def fight_duration_seconds(round_num, time_str):
    """Total elapsed fight time; None when round/time unknown."""
    if not round_num:
        return None
    sec = 0
    if time_str and ":" in str(time_str):
        try:
            m, s = str(time_str).split(":")
            sec = int(m) * 60 + int(s)
        except ValueError:
            sec = 0
    return (int(round_num) - 1) * 300 + sec


def _method_bucket(method_str):
    m = str(method_str or "").lower()
    if "dec" in m:
        return "dec"
    if "sub" in m or "choke" in m or "tap" in m:
        return "sub"
    if "ko" in m or "tko" in m:
        return "ko"
    return "other"


def evaluate_published_pick(pub, result):
    """Grade the PUBLISHED bet against the actual result.

    Returns dict: {category, winner_correct, method_claimed, method_correct,
    bet_won} where category in FULL_WIN | WINNER_ONLY | LOSS | NO_PICK.
    bet_won may be None when unsettleable (e.g. O/U without round data).
    """
    if not pub:
        return {"category": "NO_PICK", "winner_correct": None,
                "method_claimed": None, "method_correct": None, "bet_won": None}

    bt = (pub.get("bet_type") or "ml").lower()
    predicted_winner = pub.get("predicted_winner") or ""
    actual_winner = result.get("winner", "")
    actual_bucket = _method_bucket(result.get("method"))
    winner_correct = _names_match(predicted_winner, actual_winner) if predicted_winner else None

    method_claimed = bt if bt in ("ko", "sub", "dec") else None
    method_correct = None
    if method_claimed:
        method_correct = bool(winner_correct) and actual_bucket == method_claimed

    bet_won = None
    if bt == "ml":
        bet_won = bool(winner_correct)
    elif bt in ("ko", "sub", "dec"):
        bet_won = bool(method_correct)
    elif bt in ("over", "under"):
        m = re.search(r"(\d+(?:\.\d+)?)", str(pub.get("bet", "")))
        threshold = float(m.group(1)) if m else 2.5
        dur = fight_duration_seconds(result.get("round"), result.get("time"))
        if actual_bucket == "dec":
            bet_won = (bt == "over")  # went the full distance
        elif dur is not None:
            bet_won = (dur > threshold * 300) if bt == "over" else (dur < threshold * 300)
    elif bt == "distance_yes":
        bet_won = actual_bucket == "dec"
    elif bt == "distance_no":
        bet_won = actual_bucket != "dec"

    # Category for the reaction template
    if winner_correct is None:
        # Non-winner-side bet (e.g. totals) — judge purely on the bet
        if bet_won is True:
            category = "FULL_WIN"
        elif bet_won is False:
            category = "LOSS"
        else:
            category = "NO_PICK"
    elif winner_correct and (bet_won is True) and (method_correct in (None, True)):
        category = "FULL_WIN"
    elif winner_correct:
        category = "WINNER_ONLY"
    else:
        category = "LOSS"

    return {"category": category, "winner_correct": winner_correct,
            "method_claimed": method_claimed, "method_correct": method_correct,
            "bet_won": bet_won}


def get_live_results():
    """
    Poll the event page from 1_card.json for newly completed fights.
    Uses per-fight win flags — NOT the completed-events index alone.
    """
    card = load_card()
    event_url = _event_url_from_card(card)
    event_name = card.get("event", "")

    if not event_url:
        event_url, event_name = _event_url_from_completed(event_name)
    if not event_url:
        print("   ⚠️ No event URL (card missing url and completed fallback failed)")
        return []

    try:
        response = ufcstats_fetch(event_url, headers=REQUEST_HEADERS)
        if response.status_code != 200:
            print(f"   ⚠️ Event page HTTP {response.status_code}")
            return []
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"   ❌ Error fetching event page: {e}")
        return []

    results = []
    for row in soup.find_all("tr", class_="b-fight-details__table-row"):
        parsed = _parse_fight_row(row)
        if parsed:
            results.append(parsed)

    if results:
        print(f"   📋 Event: {event_name or event_url} — {len(results)} finished bout(s)")
    return results


def _fallback_reaction(winner, loser, method, outcome):
    cat = outcome.get("category", "NO_PICK")
    if cat == "FULL_WIN":
        return f"✅ CALLED IT! {winner} defeats {loser} via {method} — exactly the pick we posted. #UFC"
    if cat == "WINNER_ONLY":
        return f"✅ {winner} gets it done vs {loser} ({method}). We had the winner — the method went differently. #UFC"
    if cat == "LOSS":
        return f"❌ {winner} defeats {loser} via {method}. Our posted pick missed this one — credit where it's due. #UFC"
    return f"🚨 {winner} defeats {loser} via {method}! #UFC"


def generate_reaction(winner, loser, method, published_pick=None, outcome=None):
    """Reaction tweet locked to the graded outcome of the PUBLISHED pick.

    The old version handed the model a free 'Celebrate! Hype it up!' brief
    based on internal predictions — it claimed calls that were never tweeted,
    quoted never-published confidence numbers, and shouted CASH IT while the
    posted bet had actually lost. Now the claim template is decided in code
    from published_picks.json; the model only fills in flavor.
    """
    outcome = outcome or {"category": "NO_PICK"}
    cat = outcome.get("category", "NO_PICK")

    if not client:
        return _fallback_reaction(winner, loser, method, outcome)

    base = f"RESULT: {winner} defeats {loser} via {method}\n\n"
    pub_bet = (published_pick or {}).get("bet", "")
    pub_conf = (published_pick or {}).get("confidence")
    conf_note = ""
    if pub_conf and (published_pick or {}).get("card_published"):
        # Confidence may only be quoted when it was actually published (pick card)
        conf_note = f" (posted confidence {pub_conf}/10)"

    if cat == "FULL_WIN":
        brief = (
            f"OUR PUBLISHED PICK WON: we posted '{pub_bet}'{conf_note} before the fight and it hit.\n"
            "TONE: Celebrate confidently. You may say 'we called it' and reference the posted bet.\n"
        )
    elif cat == "WINNER_ONLY":
        brief = (
            f"PARTIAL: we posted '{pub_bet}'{conf_note} — the WINNER was right but the "
            f"bet/method did not hit as posted.\n"
            "TONE: Honest satisfaction. Credit the winner call, openly note the method/bet "
            "went differently. Do NOT say 'cash it', do NOT claim the bet won.\n"
        )
    elif cat == "LOSS":
        brief = (
            f"MISS: we posted '{pub_bet}'{conf_note} and it LOST.\n"
            "TONE: Own the miss with class. Respect the actual winner. No excuses, "
            "no fake celebration, no 'cash it'.\n"
        )
    else:  # NO_PICK
        brief = (
            "NO PUBLISHED PICK for this fight.\n"
            "TONE: Pure neutral hype about the result. You must NOT claim any prediction, "
            "pick, confidence number, or 'we called it' — we published nothing.\n"
        )

    try:
        prompt = f"""You are FightIQ, an MMA analyst bot known for HONEST accountability. React to this fight result:

{base}{brief}
Requirements:
- Maximum 250 characters (short and punchy)
- Use emojis (🚨🔥💀🩸✅❌ as fits the tone)
- Never invent picks, odds, or confidence numbers beyond what is stated above
- Add #UFC hashtag at the end

Return ONLY the tweet text, nothing else."""

        resp = client.models.generate_content(model=GEMINI_MODELS[0], contents=prompt)
        reaction = resp.text.strip()
        if len(reaction) > 280:
            reaction = reaction[:277] + "..."
        return reaction

    except Exception as e:
        print(f"   ❌ AI reaction generation failed: {e}")
        return _fallback_reaction(winner, loser, method, outcome)


def post_live_reaction(reaction_text):
    if not SocialDirector:
        print("⚠️ Social Director not available - cannot post")
        return None
    try:
        from core.twitter_client import twitter_credentials_status
        if not twitter_credentials_status()["ready"]:
            print("⚠️ Twitter not configured — set X_API_* in .env or twitter_cookies.json")
            return None
    except ImportError:
        if not os.path.exists(COOKIES_FILE):
            print(f"⚠️ Twitter cookies missing: {COOKIES_FILE}")
            return None

    try:
        director = SocialDirector.SocialDirector()
        tweet_id = director.post_tweet(reaction_text)
        if tweet_id:
            print(f"   ✅ Posted to Twitter: {tweet_id}")
        else:
            print("   ⚠️ Twitter post failed")
        return tweet_id
    except Exception as e:
        print(f"   ❌ Could not post to Twitter: {e}")
        return None


def run_live_wire_once():
    """Single poll. Returns (posted_count, finished_fight_count)."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Polling for fight results...")

    history = load_history()
    published = load_published_picks()
    live_results = get_live_results()

    if not live_results:
        print("   No finished fights on event page yet.")
        return 0, 0

    posted = 0
    for result in live_results:
        winner = result["winner"]
        loser = result["loser"]
        method = result["method"]
        fight_id = f"{winner}_vs_{loser}"

        if fight_id in history:
            print(f"   ⏭️  Already posted: {winner} vs {loser}")
            continue

        print(f"\n   🆕 NEW RESULT: {winner} defeats {loser} via {method}")

        pub = find_published_pick(published, winner, loser)
        outcome = evaluate_published_pick(pub, result)
        print(f"   🧾 Published pick: {pub.get('bet') if pub else 'NONE'} → {outcome['category']}")
        reaction = generate_reaction(winner, loser, method, pub, outcome)
        print(f"   💬 Reaction: {reaction}")

        tweet_id = post_live_reaction(reaction)
        if tweet_id:
            history[fight_id] = {
                "winner": winner,
                "loser": loser,
                "method": method,
                "round": result.get("round"),
                "time": result.get("time"),
                "published_bet": (pub or {}).get("bet"),
                "outcome": outcome["category"],
                "bet_won": outcome["bet_won"],
                "reaction": reaction,
                "tweet_id": str(tweet_id),
                "timestamp": datetime.now().isoformat(),
            }
            save_history(history)
            posted += 1
            time.sleep(10)  # Rate limit between fight tweets

    return posted, len(live_results)


def run_live_wire_continuous():
    card = load_card()
    if not is_fight_night(card):
        print("   ⏭️ Not fight night (card date ≠ today). Exiting.")
        print(f"   Card: {card.get('event', '?')} on {card.get('date', '?')}")
        return

    print("=" * 60)
    print("🔥 LIVE WIRE: REAL-TIME FIGHT NIGHT COMMENTARY")
    print("=" * 60)
    print(f"Event: {card.get('event', 'Unknown')}")
    print(f"Poll interval: {POLL_INTERVAL}s | Max runtime: {MAX_RUNTIME_HOURS}h")
    print("=" * 60)

    total_fights = len(card.get("fights", [])) or 99
    deadline = datetime.now() + timedelta(hours=MAX_RUNTIME_HOURS)
    try:
        while datetime.now() < deadline:
            _, finished = run_live_wire_once()
            if finished >= total_fights:
                print(f"\n🏁 All {total_fights} fights have results — ending early.")
                break
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n✅ Live Wire stopped by user.")
        _post_scorecard_recap()
        return

    print(f"\n✅ Live Wire window closed ({MAX_RUNTIME_HOURS}h max, early-exit on full card).")
    # End of night: score our PUBLISHED picks vs actual results and post a recap.
    _post_scorecard_recap()


def _post_scorecard_recap():
    """Generate + post the prediction-accuracy recap once the card is done."""
    try:
        from modules import _14_scorecard as Scorecard
        print("\n📊 Building end-of-night scorecard...")
        Scorecard.generate_scorecard(post=True)
    except Exception as e:
        print(f"   ⚠️ Scorecard recap failed (non-fatal): {type(e).__name__}: {str(e)[:80]}")


def main():
    parser = argparse.ArgumentParser(description="FightIQ Live Wire")
    parser.add_argument("--auto", action="store_true", help="Continuous monitoring (fight night)")
    parser.add_argument("--once", action="store_true", help="Single poll (test / manual)")
    parser.add_argument("--force", action="store_true", help="Run even if not fight night (test)")
    parser.add_argument("--scorecard", action="store_true", help="Build + post the accuracy recap and exit")
    args = parser.parse_args()

    print("--- 🔥 LIVE WIRE SYSTEM ---")

    if args.scorecard:
        _post_scorecard_recap()
        return

    if args.once or (not args.auto and not args.force):
        if not args.force and not is_fight_night():
            print("   ℹ️  Not fight night. Use --force to poll anyway.")
        n, finished = run_live_wire_once()
        print(f"   Done. Posted {n} new reaction(s) ({finished} finished on page).")
        return

    if args.auto:
        if not args.force and not is_fight_night():
            print("   ⏭️ Not fight night — cron should only run Sat/Sun on card date.")
            print(f"   Today: {datetime.now().date()} | Card date: {load_card().get('date')}")
            return
        run_live_wire_continuous()
        return

    print("Usage: python modules/_13_live_wire.py --auto | --once [--force]")


if __name__ == "__main__":
    main()
