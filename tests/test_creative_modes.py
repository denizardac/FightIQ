import sys
import os
import json
import random
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import importlib.util

# Import the module dynamically to be able to mock things
spec = importlib.util.spec_from_file_location("SpotlightEngine", "09_spotlight_engine.py")
SpotlightEngine = importlib.util.module_from_spec(spec)
sys.modules["SpotlightEngine"] = SpotlightEngine
spec.loader.exec_module(SpotlightEngine)

def mock_scrape(url):
    print(f"   [MOCK] Scraping {url}")
    return {
        "name": "Test Fighter",
        "record": "20-5-0",
        "wins": 20, "losses": 5,
        "slpm": "5.50", "sub_avg": "1.0", "str_acc": "70%", "td_avg": "2.0",
        "url": url
    }

def mock_generate_content(prompt, generation_config=None):
    print("   [MOCK] Gemini Generating content...")
    mock_resp = MagicMock()
    # Return valid JSON text based on prompt keywords to simulate different modes
    if "ORACLE" in prompt:
         data = {
            "main_tweet": "Oracle Predicts!",
            "stat_reply": "Winner is X",
            "card_stats": {"power": 90, "grappling": 90, "stamina": 90, "technique": 90, "one_liner": "Oracle"},
            "video_script": "Oracle script"
        }
    elif "VIOLENCE" in prompt:
        data = {
            "main_tweet": "Violence Alert!",
            "stat_reply": "High SLpM",
            "card_stats": {"power": 99, "grappling": 20, "stamina": 90, "technique": 50, "one_liner": "Violence"},
            "video_script": "Violence script"
        }
    elif "WOLF TICKET" in prompt or "Betting Value" in prompt:
        data = {
            "main_tweet": "WOLF TICKET ALERT!",
            "stat_reply": "Statistical Anomaly",
            "card_stats": {"power": 70, "grappling": 70, "stamina": 70, "technique": 70, "one_liner": "Anomaly"},
            "video_script": "Anomaly script"
        }
    elif "LEGEND STATUS" in prompt or "Historian" in prompt:
        data = {
            "main_tweet": "LEGEND STATUS!",
            "stat_reply": "Hall of Fame",
            "card_stats": {"power": 88, "grappling": 88, "stamina": 88, "technique": 88, "one_liner": "Legend"},
            "video_script": "Legend script"
        }
    else:
        data = {
            "main_tweet": "Standard Tweet",
            "stat_reply": "Standard Stats",
            "card_stats": {"power": 80, "grappling": 80, "stamina": 80, "technique": 80, "one_liner": "Standard"},
            "video_script": "Standard script"
        }
    mock_resp.text = json.dumps(data)
    return mock_resp

def test_mode(mode_name):
    print(f"\n🧪 TESTING MODE: {mode_name}")
    
    # Mocking
    SpotlightEngine.scrape_fighter_detailed = mock_scrape
    
    SpotlightEngine.VisualEngine = MagicMock()
    #SpotlightEngine.VisualEngine.create_stat_card.return_value = None
    
    SpotlightEngine.VideoEngine = MagicMock()
    SpotlightEngine.VideoEngine.create_reel.return_value = "mock_video.mp4"
    
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = mock_generate_content
    SpotlightEngine.get_gemini_model = MagicMock(return_value=mock_model)
    
    # Force Mode
    if mode_name == "STANDARD": weights = [1, 0, 0, 0, 0]
    elif mode_name == "VIOLENCE": weights = [0, 1, 0, 0, 0]
    elif mode_name == "ORACLE": weights = [0, 0, 1, 0, 0]
    elif mode_name == "ANOMALY": weights = [0, 0, 0, 1, 0]
    elif mode_name == "HISTORY": weights = [0, 0, 0, 0, 1]
    
    with patch('random.choices', return_value=[mode_name]):
        SpotlightEngine.main()
        
    # Check Output
    with open("spotlight_ready.json", "r") as f:
        data = json.load(f)
        
    print(f"   ✅ Output Type Check: {data['thread'][0]}")

if __name__ == "__main__":
    test_mode("STANDARD")
    test_mode("VIOLENCE")
    test_mode("ORACLE")
    test_mode("ANOMALY")
    test_mode("HISTORY")
    print("\n✅ ALL MODES PASSED!")
