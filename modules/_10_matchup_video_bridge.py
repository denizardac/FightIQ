import json
import os
import sys


# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR, MODULES_DIR

# ==========================================
# 🎬 FIGHTIQ: MATCHUP VIDEO BRIDGE
# ==========================================

AI_RESULTS_FILE = get_data_path("3_results.json")
# VISUALS_DIR is imported from core.paths

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass


# P0 FIX: Standard import instead of dynamic importlib
try:
    from modules import _10_video_engine as VideoEngine
except ImportError as e:
    print(f"❌ Error: Could not load _10_video_engine: {e}")
    sys.exit(1)


def find_radar_chart(fighter1, fighter2):
    """
    Find the radar chart PNG for a matchup.
    """
    # Clean names for filename matching
    def clean_name(name):
        return "".join([c for c in name if c.isalnum() or c == ' ']).replace(' ', '_')
    
    f1_clean = clean_name(fighter1)
    f2_clean = clean_name(fighter2)
    
    # Possible filename patterns
    patterns = [
        f"Radar_{f1_clean}_vs_{f2_clean}.png",
        f"Radar_{f2_clean}_vs_{f1_clean}.png"  # Try reversed
    ]
    
    for pattern in patterns:
        path = os.path.join(VISUALS_DIR, pattern)
        if os.path.exists(path):
            return path
    
    return None

def generate_voiceover_script(fight_brain_output):
    """
    Generate a concise voiceover script from AI analysis.
    Target: 30-45 seconds when spoken.
    """
    try:
        prediction = fight_brain_output.get('prediction', {})
        violence_score = fight_brain_output.get('violence_score', 50)
        betting_angles = fight_brain_output.get('betting_angles', {})
        
        winner = prediction.get('winner', 'Unknown')
        method = prediction.get('method', 'Decision')
        confidence = prediction.get('confidence', 5)
        
        # Extract key advantage (if available in AI output)
        key_advantage = "superior technique"  # Default
        
        safe_pick = betting_angles.get('safe_pick', {})
        
        # Check for specific advantages in betting angles reasoning
        reason = safe_pick.get('reason', '')
        if 'striking' in reason.lower():
            key_advantage = "striking advantage"
        elif 'grappling' in reason.lower() or 'wrestling' in reason.lower():
            key_advantage = "grappling dominance"
        elif 'ko' in reason.lower() or 'power' in reason.lower():
            key_advantage = "knockout power"
        elif 'submission' in reason.lower():
            key_advantage = "submission skills"
        
        # Build script
        script = f"The FightIQ Oracle predicts: {winner} wins via {method}, "
        script += f"with {confidence} out of 10 confidence. "
        
        if violence_score >= 80:
            script += f"This is a guaranteed violence fest, rated {violence_score} out of 100. "
        elif violence_score >= 60:
            script += f"Expect action with a violence score of {violence_score}. "
        
        script += f"{winner}'s {key_advantage} is the deciding factor in this matchup. "
        
        # Add betting angle if available
        if safe_pick.get('bet'):
            script += f"Betting value detected: {safe_pick['bet']}. "
        
        script += "Stay sharp."
        
        return script
        
    except Exception as e:
        print(f"   ⚠️ Script generation error: {e}")
        return "The FightIQ Oracle has spoken. Analysis complete. Stay sharp."

def main():
    print("--- 🎬 MATCHUP VIDEO BRIDGE ---")
    
    # Load AI predictions
    if not os.path.exists(AI_RESULTS_FILE):
        print(f"❌ '{AI_RESULTS_FILE}' not found. Run step 05 first.")
        return
    
    try:
        with open(AI_RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as e:
        print(f"❌ Error loading results: {e}")
        return
    
    if not os.path.exists(VISUALS_DIR):
        print(f"❌ '{VISUALS_DIR}' directory not found.")
        return
    
    # Process each fight
    videos_generated = []
    
    for i, item in enumerate(results):
        matchup = item.get('matchup', 'Unknown vs Unknown')
        brain_output = item.get('fight_brain_output', {})
        
        # Extract fighter names
        if ' vs ' not in matchup:
            print(f"⚠️ Skipping invalid matchup format: {matchup}")
            continue
        
        fighters = matchup.split(' vs ')
        if len(fighters) != 2:
            continue
        
        f1_name, f2_name = fighters[0].strip(), fighters[1].strip()
        
        print(f"\n🎥 [{i+1}/{len(results)}] Processing: {f1_name} vs {f2_name}")
        
        # Find radar chart
        radar_path = find_radar_chart(f1_name, f2_name)
        
        if not radar_path:
            print(f"   ⚠️ Radar chart not found, skipping video.")
            continue
        
        print(f"   ✅ Found radar: {radar_path}")
        
        # Generate voiceover script
        script = generate_voiceover_script(brain_output)
        print(f"   📝 Script: {script[:60]}...")
        
        # Generate video
        try:
            video_path = VideoEngine.create_matchup_reel(
                radar_path,
                script,
                f1_name,
                f2_name
            )
            
            if video_path:
                print(f"   ✅ Video created: {video_path}")
                videos_generated.append(video_path)
            else:
                print(f"   ⚠️ Video generation returned None.")
        
        except Exception as e:
            print(f"   ❌ Video generation failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE: Generated {len(videos_generated)} matchup videos.")
    print(f"📊 Success Rate: {len(videos_generated)}/{len(results)} fights")
    
    if videos_generated:
        print(f"\n📁 Videos saved:")
        for video in videos_generated[:5]:  # Show first 5
            print(f"   - {video}")
        if len(videos_generated) > 5:
            print(f"   ... and {len(videos_generated) - 5} more")

if __name__ == "__main__":
    main()
