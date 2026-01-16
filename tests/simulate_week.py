import sys
import os
import json
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock
import time

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import importlib.util
spec = importlib.util.spec_from_file_location("SpotlightEngine", "09_spotlight_engine.py")
SpotlightEngine = importlib.util.module_from_spec(spec)
sys.modules["SpotlightEngine"] = SpotlightEngine
spec.loader.exec_module(SpotlightEngine)

OUTPUT_DIR = "simulations"

def run_simulation():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    print("--- 📅 STARTING WEEKLY SIMULATION ---")
    
    # Days to simulate: Mon(0) to Fri(4)
    days = [
        (0, "Monday", "Standard/Balanced"),
        (1, "Tuesday", "Oracle/Polls"),
        (2, "Wednesday", "Violence"),
        (3, "Thursday", "History/Throwback"),
        (4, "Friday", "Anomaly/Betting")
    ]
    
    for day_idx, day_name, note in days:
        print(f"\n🌞 SIMULATING: {day_name} ({note})")
        
        class MockDate(datetime):
            @classmethod
            def today(cls):
                d = datetime.now()
                return d.replace(year=2024, month=1, day=1+day_idx)
                
        with patch('SpotlightEngine.datetime', MockDate):
             # Mock Video Engine to save time
             SpotlightEngine.VideoEngine = MagicMock()
             SpotlightEngine.VideoEngine.create_reel.return_value = "simulated_video.mp4"
             
             try:
                 SpotlightEngine.main()
                 
                 # Read result
                 if os.path.exists("spotlight_ready.json"):
                     with open("spotlight_ready.json", "r") as f:
                         data = json.load(f)
                     
                     # Determine Mode from output to verify
                     mode_used = "UNKNOWN"
                     if "poll_options" in data and data['poll_options']: mode_used = "ORACLE"
                     elif "Violence" in str(data): mode_used = "VIOLENCE"
                     elif "ODDS:" in str(data): mode_used = "ANOMALY"
                     elif "LEGEND" in str(data): mode_used = "HISTORY"
                     else: mode_used = "STANDARD"
                     
                     filename = f"{OUTPUT_DIR}/{day_name}_{mode_used}.json"
                     shutil.copy("spotlight_ready.json", filename)
                     print(f"   ✅ Saved: {filename}")
                 else:
                     print("   ❌ No output generated.")
                     
             except Exception as e:
                 print(f"   ❌ Error: {e}")
                 
        time.sleep(1)

    print(f"\n🎉 Simulation Complete. Check '{OUTPUT_DIR}' folder.")

if __name__ == "__main__":
    run_simulation()
