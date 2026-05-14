import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from datetime import datetime
import time
from google import genai
from dotenv import load_dotenv


# ==========================================
# 🔥 FIGHTIQ: LIVE WIRE (Real-Time Commentary)
# ==========================================

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

# P0 FIX: Standard import at module level
try:
    from modules import _08_social_director as SocialDirector
except ImportError:
    SocialDirector = None


try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Load environment
load_dotenv()

# Files
CARD_FILE = get_data_path("1_card.json")
RESULTS_FILE = get_data_path("3_results.json")
LIVE_WIRE_HISTORY = get_data_path("live_wire_history.json")

# Configuration
try:
    import core.config as config
    POLL_INTERVAL = config.LIVE_WIRE_POLL_INTERVAL
    GEMINI_MODELS = config.GEMINI_MODELS
except ImportError:
    print("⚠️ config.py not found using defaults")
    POLL_INTERVAL = 60
    GEMINI_MODELS = ["models/gemini-exp-1206", "models/gemini-2.0-flash-exp"]

# Setup Gemini
api_key = os.getenv("GEMINI_API_KEY")
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"⚠️ GenAI Client Init Error: {e}")

UFC_STATS_URL = "http://ufcstats.com/statistics/events/completed"


def load_history():
    """Load history of posted reactions."""
    if os.path.exists(LIVE_WIRE_HISTORY):
        try:
            with open(LIVE_WIRE_HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history):
    """Persist history of posted reactions."""
    try:
        with open(LIVE_WIRE_HISTORY, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠️ Could not save live wire history: {e}")


def get_live_results():
    """
    Poll UFCStats completed events page for fight results from today's event.
    Returns a list of dicts: [{winner, loser, method}, ...]
    """
    try:
        response = requests.get(UFC_STATS_URL, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        event_rows = soup.find_all("tr", class_="b-statistics__table-row")
        if not event_rows:
            return []

        # Most recent completed event is the first row with a link
        first_event = None
        for row in event_rows:
            if row.find("a"):
                first_event = row
                break
        if not first_event:
            return []

        event_link = first_event.find("a", class_="b-link") or first_event.find("a")
        if not event_link:
            return []

        event_url = event_link["href"]
        event_name = event_link.text.strip()

        # Verify this is today's expected event (fuzzy: any shared word)
        try:
            with open(CARD_FILE, "r", encoding="utf-8") as f:
                card_data = json.load(f)
                expected_event = card_data.get("event", "")
                if expected_event:
                    a = set(w.lower() for w in event_name.split() if len(w) > 3)
                    b = set(w.lower() for w in expected_event.split() if len(w) > 3)
                    if a and b and not (a & b):
                        print(f"   Event mismatch: '{event_name}' vs expected '{expected_event}'")
                        return []
        except Exception:
            pass  # No card file — proceed anyway

        # Fetch fight results from event detail page
        response = requests.get(event_url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        fight_rows = soup.find_all("tr", class_="b-fight-details__table-row")

        for row in fight_rows[1:]:  # Skip header
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            fighters_col = cols[1]
            fighter_links = fighters_col.find_all("a")
            if len(fighter_links) < 2:
                continue

            f1_name = fighter_links[0].text.strip()
            f2_name = fighter_links[1].text.strip()

            # Determine winner by checking each link's parent paragraph for
            # the win flag class. Falls back to first-listed-is-winner.
            def _is_winner(link):
                node = link
                for _ in range(4):
                    node = node.parent if node else None
                    if not node:
                        break
                    cls = " ".join(node.get("class", [])) if hasattr(node, "get") else ""
                    if "win" in cls:
                        return True
                return False

            if _is_winner(fighter_links[0]):
                winner, loser = f1_name, f2_name
            elif _is_winner(fighter_links[1]):
                winner, loser = f2_name, f1_name
            elif "b-fight-details__table-text_win" in str(cols[1]):
                winner, loser = f1_name, f2_name
            else:
                # No definitive marker — skip this fight rather than guessing
                continue

            method_col = cols[7] if len(cols) > 7 else None
            method = method_col.text.strip() if method_col else "Decision"

            results.append({"winner": winner, "loser": loser, "method": method})

        return results

    except Exception as e:
        print(f"   ❌ Error fetching live results: {e}")
        return []


def generate_reaction(winner, loser, method, our_prediction=None):
    if not client:
        return f"🚨 {winner} defeats {loser} via {method}! #UFC"

    try:
        prompt = f"""You are FightIQ, a hyped MMA analyst bot. React to this fight result with maximum energy:

RESULT: {winner} defeats {loser} via {method}

"""
        # Add prediction context
        if our_prediction:
            predicted_winner = our_prediction.get('winner', '')
            predicted_method = our_prediction.get('method', '')
            confidence = our_prediction.get('confidence', 5)
            
            if predicted_winner.lower() == winner.lower():
                prompt += f"OUR PREDICTION: ✅ We called {predicted_winner} via {predicted_method} (Confidence: {confidence}/10)\n"
                prompt += "TONE: Celebrate being right! Hype it up!\n"
            else:
                prompt += f"OUR PREDICTION: ❌ We predicted {predicted_winner} (they lost)\n"
                prompt += "TONE: Shocked but respectful. Acknowledge the upset.\n"
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
        
        # Generate — use first available model from config
        resp = client.models.generate_content(
            model=GEMINI_MODELS[0],
            contents=prompt
        )
        reaction = resp.text.strip()
        
        # Safety check length
        if len(reaction) > 280:
            reaction = reaction[:277] + "..."
        
        return reaction
    
    except Exception as e:
        print(f"   ❌ AI reaction generation failed: {e}")
        return f"🚨 {winner} defeats {loser} via {method}! #UFC"

def post_live_reaction(reaction_text):
    """
    Post reaction to Twitter.
    Uses SocialDirector if available.
    """
    try:
        # P0 FIX: Use module-level import instead of dynamic
        if not SocialDirector:
            print("⚠️ Social Director not available - cannot post")
            return False
        
        # Create instance and post
        director = SocialDirector.SocialDirector()
        tweet_id = director.post_tweet(reaction_text)
        
        if tweet_id:
            print(f"   ✅ Posted to Twitter: {tweet_id}")
            return tweet_id
        else:
            print(f"   ⚠️ Twitter post failed")
            return None
    
    except Exception as e:
        print(f"   ❌ Could not post to Twitter: {e}")
        return None

def run_live_wire_once():
    """
    Single poll cycle: Check for new results and post reactions.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Polling for fight results...")
    
    # Load history
    history = load_history()
    
    # Get our predictions
    predictions = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                results_data = json.load(f)
                for item in results_data:
                    matchup = item.get('matchup', '')
                    brain = item.get('fight_brain_output', {})
                    prediction = brain.get('prediction', {})
                    predictions[matchup] = prediction
        except:
            pass
    
    # Get live results
    live_results = get_live_results()
    
    if not live_results:
        print("   No new results detected.")
        return
    
    print(f"   Found {len(live_results)} completed fights.")
    
    # Process each result
    for result in live_results:
        winner = result['winner']
        loser = result['loser']
        method = result['method']
        
        # Create unique ID
        fight_id = f"{winner}_vs_{loser}"
        
        # Check if already posted
        if fight_id in history:
            print(f"   ⏭️  Already posted reaction for {winner} vs {loser}")
            continue
        
        print(f"\n   🆕 NEW RESULT: {winner} defeats {loser} via {method}")
        
        # Find our prediction
        matchup_key = f"{winner} vs {loser}"
        our_prediction = predictions.get(matchup_key) or predictions.get(f"{loser} vs {winner}")
        
        # Generate reaction
        reaction = generate_reaction(winner, loser, method, our_prediction)
        print(f"   💬 Reaction: {reaction}")
        
        # Post to Twitter
        tweet_id = post_live_reaction(reaction)
        
        if tweet_id:
            # Save to history
            history[fight_id] = {
                'winner': winner,
                'loser': loser,
                'method': method,
                'reaction': reaction,
                'tweet_id': tweet_id,
                'timestamp': datetime.now().isoformat()
            }
            save_history(history)

def run_live_wire_continuous():
    """
    Continuous monitoring mode: Poll every 60 seconds during event hours.
    """
    print("="*60)
    print("🔥 LIVE WIRE: REAL-TIME FIGHT NIGHT COMMENTARY")
    print("="*60)
    print(f"Poll Interval: {POLL_INTERVAL} seconds")
    print(f"Press Ctrl+C to stop")
    print("="*60)
    
    try:
        while True:
            run_live_wire_once()
            time.sleep(POLL_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n✅ Live Wire stopped by user.")

import argparse

def main():
    parser = argparse.ArgumentParser(description="FightIQ Live Wire")
    parser.add_argument("--auto", action="store_true", help="Run in continuous monitoring mode automatically")
    args = parser.parse_args()

    print("--- 🔥 LIVE WIRE SYSTEM ---")
    
    if args.auto:
        print("   🚀 Auto Mode Activated: Starting Continuous Monitoring...")
        run_live_wire_continuous()
        return

    print("\nOptions:")
    print("1. Run single poll (test mode)")
    print("2. Run continuous monitoring (fight night mode)")
    
    choice = input("\nSelect option (1-2): ").strip()
    
    if choice == "1":
        run_live_wire_once()
    elif choice == "2":
        run_live_wire_continuous()
    else:
        print("Invalid option")

if __name__ == "__main__":
    main()
