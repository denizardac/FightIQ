import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from datetime import datetime
import time
from google import genai
from dotenv import load_dotenv
import importlib.util

# ==========================================
# 🔥 FIGHTIQ: LIVE WIRE (Real-Time Commentary)
# ==========================================

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Load environment
load_dotenv()

# Files
CARD_FILE = "1_card.json"
RESULTS_FILE = "3_results.json"
LIVE_WIRE_HISTORY = "live_wire_history.json"

# Configuration
POLL_INTERVAL = 60  # Check every 60 seconds
UFC_STATS_URL = "http://ufcstats.com/statistics/events/completed"

# Import config
try:
    import config
    GEMINI_MODELS = config.GEMINI_MODELS
except:
    GEMINI_MODELS = ["models/gemini-exp-1206", "models/gemini-2.0-flash-exp"]

# Setup Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def load_history():
    """Load history of posted reactions"""
    if os.path.exists(LIVE_WIRE_HISTORY):
        try:
            with open(LIVE_WIRE_HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history):
    """Save history"""
    with open(LIVE_WIRE_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def get_live_results():
    """
    Poll UFC Stats for completed fights from today's event.
    Returns list of fight results: [(winner, loser, method), ...]
    """
    try:
        response = requests.get(UFC_STATS_URL, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the most recent event (first in completed list)
        event_rows = soup.find_all('tr', class_='b-statistics__table-row')
        
        if not event_rows:
            return []
        
        # Get first event (most recent)
        first_event = event_rows[0]
        event_link = first_event.find('a', class_='b-link')
        
        if not event_link:
            return []
        
        event_url = event_link['href']
        event_name = event_link.text.strip()
        
        # Check if this is today's event
        # Load our card file to compare
        try:
            with open(CARD_FILE, "r", encoding="utf-8") as f:
                card_data = json.load(f)
                expected_event = card_data.get('event', '')
                
                # Simple name matching
                if event_name.lower() not in expected_event.lower():
                    print(f"   Event mismatch: {event_name} vs {expected_event}")
                    return []
        except:
            pass
        
        # Fetch fight results from event page
        response = requests.get(event_url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')
        
        for row in fight_rows[1:]:  # Skip header
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            
            # Extract fighter names
            fighters_col = cols[1]
            fighter_links = fighters_col.find_all('a')
            
            if len(fighter_links) >= 2:
                f1_name = fighter_links[0].text.strip()
                f2_name = fighter_links[1].text.strip()
                
                # Determine winner (first fighter has class 'b-fight-details__table-text_win')
                if 'b-fight-details__table-text_win' in str(cols[1]):
                    winner = f1_name
                    loser = f2_name
                else:
                    winner = f2_name
                    loser = f1_name
                
                # Get method
                method_col = cols[7] if len(cols) > 7 else None
                method = method_col.text.strip() if method_col else "Decision"
                
                results.append({
                    'winner': winner,
                    'loser': loser,
                    'method': method
                })
        
        return results
    
    except Exception as e:
        print(f"   ❌ Error fetching live results: {e}")
        return []

def generate_reaction(winner, loser, method, our_prediction=None):
    """
    Generate spicy AI reaction to fight result.
    
    Args:
        winner: Winner name
        loser: Loser name
        method: Finish method (KO, SUB, DEC)
        our_prediction: Our prediction dict (optional)
    
    Returns:
        str: Tweet-ready reaction
    """
    try:
        # Select model
        model = None
        for model_name in GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                break
            except:
                continue
        
        if not model:
            return f"🚨 {winner} defeats {loser} via {method}! #UFC"
        
        # Build prompt
        prompt = f"""You are FightIQ, a hyped MMA analyst bot. React to this fight result with maximum energy:

RESULT: {winner} defeats {loser} via {method}

"""
        
        # Add prediction context if available
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
        
        # Generate
        response = model.generate_content(prompt)
        reaction = response.text.strip()
        
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
        # Import social director
        import importlib.util
        spec = importlib.util.spec_from_file_location("SocialDirector", "08_social_director.py")
        social_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(social_module)
        
        # Create instance and post
        director = social_module.SocialDirector()
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

def main():
    print("--- 🔥 LIVE WIRE SYSTEM ---")
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
