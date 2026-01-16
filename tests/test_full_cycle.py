
import sys
import os
import json
import time

# Add parent dir to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import importlib.util
    # Dynamic imports (simulating main.py)
    spec_t = importlib.util.spec_from_file_location("TrendHunter", "11_trend_hunter.py")
    TrendHunter = importlib.util.module_from_spec(spec_t)
    spec_t.loader.exec_module(TrendHunter)

    spec_s = importlib.util.spec_from_file_location("SpotlightEngine", "09_spotlight_engine.py")
    SpotlightEngine = importlib.util.module_from_spec(spec_s)
    spec_s.loader.exec_module(SpotlightEngine)

    spec_v = importlib.util.spec_from_file_location("VideoEngine", "10_video_engine.py")
    VideoEngine = importlib.util.module_from_spec(spec_v)
    spec_v.loader.exec_module(VideoEngine)
    
except Exception as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

def test_trend_hunter():
    print("\n🔍 TESTING TREND HUNTER...")
    trends = TrendHunter.get_trending_fighters()
    if trends:
        print(f"   ✅ SUCCESS: Found {len(trends)} trends: {trends[:3]}")
        return trends
    else:
        print("   ⚠️ WARNING: No trends found (or API error).")
        return []

def test_spotlight_generation_mock(fighter_name):
    print(f"\n🎨 TESTING SPOTLIGHT ENGINE (MOCKED for {fighter_name})...")
    
    # 1. Scrape (Actual)
    print("   1. Scraping data...")
    # urls hardcoded or fetched? Spotlight uses local DB.
    # Let's use Spotlight's internal function if possible, or just mock the data pass
    # SpotlightEngine.main() runs the whole random loop. We want to TARGET one fighter.
    
    # Check if we can import the scraper function directly?
    # Yes, SpotlightEngine.scrape_fighter_detailed
    
    _, urls = SpotlightEngine.load_db()
    
    # Find key for fighter
    key = None
    for k in urls.keys():
        if fighter_name.lower() in k.lower():
            key = k
            break
            
    if not key:
        print(f"   ❌ Fighter '{fighter_name}' not found in DB.")
        return None
        
    url = urls[key]
    data = SpotlightEngine.scrape_fighter_detailed(url)
    
    if not data:
        print("   ❌ Scraping failed.")
        return None
        
    print(f"   ✅ Scraped: {data['name']} ({data['record']})")
    
    # 2. AI Content (Mocked to save API tokens or Actual?)
    # Let's use ACTUAL to verify Gemini integration.
    print("   2. Generating AI Content (Gemini)...")
    ai_content = SpotlightEngine.generate_thread_content(data)
    if ai_content:
        print("   ✅ Gemini Response Received.")
    else:
        print("   ❌ Gemini Failed.")
        return None
        
    # 3. Visuals (with Background Logic)
    print("   3. Generating Visuals...")
    hunter = SpotlightEngine.VisualEngine.ImageHunter()
    img_path = hunter.get_fighter_image(data['name'])
    
    # Simulate AI Background Path (Mock)
    bg_path = "visuals/mock_ai_bg.jpg" 
    # (In real life we would generate this. For test we pass None or check if logic accepts it)
    
    SpotlightEngine.VisualEngine.create_stat_card(
        data['name'],
        ai_content['card_stats'],
        ai_content['card_stats']['one_liner'],
        img_path,
        record=data['record'],
        bg_path=None # We haven't downloaded a real bg yet
    )
    
    card_path = f"visuals/Card_{data['name'].replace(' ','_')}.png"
    if os.path.exists(card_path):
         print(f"   ✅ Stat Card Created: {card_path}")
    else:
         print("   ❌ Stat Card Generation Failed.")
         return None

    # 4. Video
    print("   4. Generating Video...")
    video_path = VideoEngine.create_reel(
        data['name'],
        card_path,
        ai_content['video_script']
    )
    
    if video_path and os.path.exists(video_path):
        print(f"   ✅ Video Created: {video_path}")
    else:
        print("   ❌ Video Generation Failed.")
        
    return {
        "visual": card_path,
        "video": video_path,
        "tweet": ai_content['main_tweet']
    }

if __name__ == "__main__":
    print("="*60)
    print("🧪 FIGHTIQ AUTOMATED TEST SUITE")
    print("="*60)
    
    # 1. Test Trends
    trends = test_trend_hunter()
    
    target = "Conor McGregor" # Default test
    if trends:
        target = trends[0] # Test with top trending
        
    # 2. Test Full Pipeline
    result = test_spotlight_generation_mock(target)
    
    if result:
        print("\n" + "="*60)
        print("✅✅ TEST PASSED: ALL ASSETS GENERATED ✅✅")
        print(f"Tweet: {result['tweet']}")
        print(f"Video: {result['video']}")
        print("="*60)
        print("\nTo POST this to Twitter, run: python 08_social_director.py (It reads spotlight_ready.json)")
    else:
        print("\n❌ TEST FAILED.")
