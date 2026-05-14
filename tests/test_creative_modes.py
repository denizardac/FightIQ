"""
FightIQ Creative Modes Test
Tests all 5 IDLE content modes with mocked AI and visual dependencies.
Does NOT make real Gemini/scraping calls.
"""

import sys
import os
import json
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.paths import get_data_path

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "SpotlightEngine",
    os.path.join(PROJECT_ROOT, "modules", "_09_spotlight_engine.py")
)
SpotlightEngine = importlib.util.module_from_spec(_spec)
sys.modules["SpotlightEngine"] = SpotlightEngine
_spec.loader.exec_module(SpotlightEngine)


def _mock_ai_response(client, model_name, prompt):
    """Return mode-appropriate mock AI content."""
    mock_resp = MagicMock()
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
    elif "LEGEND STATUS" in prompt or "Historian" in prompt or "HISTORY" in prompt:
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

    # Patch heavy dependencies
    SpotlightEngine.scrape_fighter_detailed = lambda url: {
        "name": "Test Fighter", "record": "20-5-0",
        "wins": 20, "losses": 5,
        "slpm": "5.50", "sub_avg": "1.0", "str_acc": "70%", "td_avg": "2.0",
        "url": url
    }
    SpotlightEngine.VisualEngine = MagicMock()
    SpotlightEngine.VideoEngine = MagicMock()
    SpotlightEngine.VideoEngine.create_reel.return_value = "mock_video.mp4"
    SpotlightEngine.generate_with_retry = _mock_ai_response

    with patch("random.choices", return_value=[mode_name]):
        SpotlightEngine.main()

    # Verify output was written to data/spotlight_ready.json
    output_path = get_data_path("spotlight_ready.json")
    assert os.path.exists(output_path), f"spotlight_ready.json not found at {output_path}"

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "thread" in data, "Output missing 'thread' key"
    print(f"   ✅ Mode {mode_name} OK: {data['thread'][0][:60]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 FIGHTIQ CREATIVE MODES TEST")
    print("=" * 60)

    test_mode("STANDARD")
    test_mode("VIOLENCE")
    test_mode("ORACLE")
    test_mode("ANOMALY")
    test_mode("HISTORY")

    print("\n✅ ALL MODES PASSED!")
