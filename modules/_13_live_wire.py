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
    Current layout (2026): col0 = win flag, col1 = two fighters (winner listed first).
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

    return {"winner": winner, "loser": loser, "method": method}


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


def generate_reaction(winner, loser, method, our_prediction=None):
    if not client:
        return f"🚨 {winner} defeats {loser} via {method}! #UFC"

    try:
        prompt = f"""You are FightIQ, a hyped MMA analyst bot. React to this fight result with maximum energy:

RESULT: {winner} defeats {loser} via {method}

"""
        if our_prediction:
            predicted_winner = our_prediction.get("winner", "")
            predicted_method = our_prediction.get("method", "")
            confidence = our_prediction.get("confidence", 5)

            if predicted_winner.lower() in winner.lower() or winner.lower() in predicted_winner.lower():
                prompt += (
                    f"OUR PREDICTION: ✅ We called {predicted_winner} via {predicted_method} "
                    f"(Confidence: {confidence}/10)\n"
                    "TONE: Celebrate being right! Hype it up!\n"
                )
            else:
                prompt += (
                    f"OUR PREDICTION: ❌ We predicted {predicted_winner} (they lost)\n"
                    "TONE: Shocked but respectful. Acknowledge the upset.\n"
                )
        else:
            prompt += "TONE: Pure hype, unbiased reaction.\n"

        prompt += """
Requirements:
- Maximum 250 characters (short and punchy)
- Use emojis (🚨🔥💀🩸👑)
- Be energetic and engaging
- Add #UFC hashtag at the end
- Sound like a real MMA fan, not a robot

Return ONLY the tweet text, nothing else."""

        resp = client.models.generate_content(model=GEMINI_MODELS[0], contents=prompt)
        reaction = resp.text.strip()
        if len(reaction) > 280:
            reaction = reaction[:277] + "..."
        return reaction

    except Exception as e:
        print(f"   ❌ AI reaction generation failed: {e}")
        return f"🚨 {winner} defeats {loser} via {method}! #UFC"


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


def _load_predictions():
    predictions = {}
    if not os.path.exists(RESULTS_FILE):
        return predictions
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for item in json.load(f):
                matchup = item.get("matchup", "")
                brain = item.get("fight_brain_output", {})
                if matchup and brain.get("prediction"):
                    predictions[matchup] = brain["prediction"]
    except Exception:
        pass
    return predictions


def _find_prediction(predictions, winner, loser):
    for key in (f"{winner} vs {loser}", f"{loser} vs {winner}"):
        if key in predictions:
            return predictions[key]
    w_low, l_low = winner.lower(), loser.lower()
    for matchup, pred in predictions.items():
        if " vs " not in matchup:
            continue
        if w_low in matchup.lower() and l_low in matchup.lower():
            return pred
    return None


def run_live_wire_once():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Polling for fight results...")

    history = load_history()
    predictions = _load_predictions()
    live_results = get_live_results()

    if not live_results:
        print("   No finished fights on event page yet.")
        return 0

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

        our_prediction = _find_prediction(predictions, winner, loser)
        reaction = generate_reaction(winner, loser, method, our_prediction)
        print(f"   💬 Reaction: {reaction}")

        tweet_id = post_live_reaction(reaction)
        if tweet_id:
            history[fight_id] = {
                "winner": winner,
                "loser": loser,
                "method": method,
                "reaction": reaction,
                "tweet_id": str(tweet_id),
                "timestamp": datetime.now().isoformat(),
            }
            save_history(history)
            posted += 1
            time.sleep(10)  # Rate limit between fight tweets

    return posted


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

    deadline = datetime.now() + timedelta(hours=MAX_RUNTIME_HOURS)
    try:
        while datetime.now() < deadline:
            run_live_wire_once()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n✅ Live Wire stopped by user.")
        _post_scorecard_recap()
        return

    print(f"\n✅ Live Wire finished after {MAX_RUNTIME_HOURS}h window.")
    # End of night: score our predictions vs actual results and post a recap.
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
        n = run_live_wire_once()
        print(f"   Done. Posted {n} new reaction(s).")
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
