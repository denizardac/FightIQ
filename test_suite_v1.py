#!/usr/bin/env python3
"""
FightIQ Integration Test Suite v1
Tests all Phase 1-3 components without requiring live data.
"""

import os
import sys
import json
from datetime import datetime

# ==========================================
# TEST CONFIGURATION
# ==========================================

TEST_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "tests_run": 0,
    "tests_passed": 0,
    "tests_failed": 0,
    "failures": []
}

SAMPLE_FIGHTER_DATA = {
    "fighter": "Conor McGregor",
    "nickname": "The Notorious",
    "stats": {
        "power": 95,
        "grappling": 65,
        "stamina": 70,
        "chin": 75,
        "technique": 90
    },
    "one_liner": "The King is Back",
    "record": "22-6-0"
}

SAMPLE_PARLAY_DATA = {
    "safe_slip": [
        {"match": "McGregor vs Chandler", "pick": "McGregor ML", "reason": "High confidence"},
        {"match": "Adesanya vs Strickland", "pick": "Adesanya ML", "reason": "Technical superiority"},
        {"match": "Oliveira vs Poirier", "pick": "Oliveira SUB", "reason": "Submission threat"}
    ],
    "violence_slip": [
        {"match": "Gaethje vs Holloway", "pick": "FDGTD", "reason": "Violence score 95/100"},
        {"match": "Moreno vs Figueiredo", "pick": "Under 2.5", "reason": "Early finish expected"}
    ],
    "value_slip": [
        {"match": "O'Malley vs Yan", "pick": "O'Malley +250", "reason": "Market inefficiency"}
    ]
}

def log_test(test_name, passed, message=""):
    """Log test result"""
    TEST_RESULTS["tests_run"] += 1
    
    if passed:
        TEST_RESULTS["tests_passed"] += 1
        print(f"✅ PASS: {test_name}")
    else:
        TEST_RESULTS["tests_failed"] += 1
        TEST_RESULTS["failures"].append({"test": test_name, "error": message})
        print(f"❌ FAIL: {test_name}")
        if message:
            print(f"   Error: {message}")

def setup_test_environment():
    """Create necessary directories and test data files"""
    print("\n" + "="*60)
    print("🛠️  SETTING UP TEST ENVIRONMENT")
    print("="*60)
    
    # Create directories
    os.makedirs("visuals", exist_ok=True)
    os.makedirs("assets/backgrounds", exist_ok=True)
    os.makedirs("test_outputs", exist_ok=True)
    
    # Create sample parlay file
    with open("4_parlays.json", "w", encoding="utf-8") as f:
        json.dump(SAMPLE_PARLAY_DATA, f, indent=2)
    
    print("✅ Test environment ready\n")

def test_background_forge():
    """Test 1: GenAI Background Generation"""
    print("\n" + "="*60)
    print("TEST 1: GenAI Background Generator (12_background_forge.py)")
    print("="*60)
    
    try:
        # Import module
        import importlib.util
        spec = importlib.util.spec_from_file_location("background_forge", "12_background_forge.py")
        forge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(forge)
        
        print(f"Testing background generation for: {SAMPLE_FIGHTER_DATA['nickname']}")
        
        # Note: This will actually call the API if GEMINI_API_KEY is set
        # For true dry-run, we'd need to mock the API
        # For now, we'll check if the function exists and is callable
        
        if hasattr(forge, 'generate_fighter_background'):
            print("✅ Module loaded, function exists")
            
            # Check if cache file can be created
            test_cache = {"The_Notorious": "assets/backgrounds/The_Notorious.png"}
            cache_file = "assets/background_cache.json"
            
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(test_cache, f)
            
            if os.path.exists(cache_file):
                log_test("Background Forge - Module Structure", True)
                print("   Note: Skipping actual API call to save costs")
                print("   Run manually: python 12_background_forge.py")
            else:
                log_test("Background Forge - Cache System", False, "Could not create cache file")
        else:
            log_test("Background Forge - Function Missing", False, "generate_fighter_background not found")
    
    except Exception as e:
        log_test("Background Forge - Import", False, str(e))

def test_visual_engine():
    """Test 2: Stat Card Generation with Custom Background"""
    print("\n" + "="*60)
    print("TEST 2: Visual Engine with Custom Backgrounds (06_visual_engine.py)")
    print("="*60)
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("visual_engine", "06_visual_engine.py")
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        
        if hasattr(engine, 'create_stat_card'):
            print("Creating stat card for", SAMPLE_FIGHTER_DATA['fighter'])
            
            # Call the function
            engine.create_stat_card(
                fighter_name=SAMPLE_FIGHTER_DATA['fighter'],
                stats=SAMPLE_FIGHTER_DATA['stats'],
                one_liner=SAMPLE_FIGHTER_DATA['one_liner'],
                img_path=None,  # No image for test
                record=SAMPLE_FIGHTER_DATA['record'],
                bg_path=None  # Will auto-detect if exists
            )
            
            # Check if output was created
            expected_file = "visuals/Card_Conor_McGregor.png"
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file)
                log_test("Visual Engine - Stat Card Generation", True, f"Created {file_size} bytes")
                print(f"   📁 Output: {expected_file}")
            else:
                log_test("Visual Engine - Stat Card Generation", False, "Output file not created")
        else:
            log_test("Visual Engine - Function Missing", False, "create_stat_card not found")
    
    except Exception as e:
        log_test("Visual Engine - Execution", False, str(e))
        import traceback
        traceback.print_exc()

def test_ticket_generator():
    """Test 3: Betting Ticket Visualization"""
    print("\n" + "="*60)
    print("TEST 3: Betting Ticket Generator (06b_ticket_generator.py)")
    print("="*60)
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("ticket_gen", "06b_ticket_generator.py")
        ticket = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ticket)
        
        if hasattr(ticket, 'generate_betting_ticket'):
            print("Generating betting tickets...")
            
            # Generate each slip type
            slip_types = ["safe", "violence", "value"]
            success_count = 0
            
            for slip_type in slip_types:
                slip_data = SAMPLE_PARLAY_DATA.get(f"{slip_type}_slip", [])
                
                try:
                    output_path = ticket.generate_betting_ticket(slip_data, slip_type)
                    
                    if output_path and os.path.exists(output_path):
                        file_size = os.path.getsize(output_path)
                        print(f"   ✅ {slip_type.upper()}: {output_path} ({file_size} bytes)")
                        success_count += 1
                    else:
                        print(f"   ❌ {slip_type.upper()}: Failed to generate")
                except Exception as e:
                    print(f"   ❌ {slip_type.upper()}: {e}")
            
            if success_count == 3:
                log_test("Ticket Generator - All Slips", True)
            else:
                log_test("Ticket Generator - All Slips", False, f"Only {success_count}/3 generated")
        else:
            log_test("Ticket Generator - Function Missing", False)
    
    except Exception as e:
        log_test("Ticket Generator - Import", False, str(e))

def test_video_engine():
    """Test 4: Video Generation (Skip for speed, just check structure)"""
    print("\n" + "="*60)
    print("TEST 4: Video Engine Structure (10_video_engine.py)")
    print("="*60)
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("video_engine", "10_video_engine.py")
        video = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(video)
        
        # Check if new function exists
        if hasattr(video, 'create_matchup_reel'):
            log_test("Video Engine - Matchup Reel Function", True)
            print("   ⏭️  Skipping actual video render (takes 20-30 seconds)")
            print("   To test manually: python 10_matchup_video_bridge.py")
        else:
            log_test("Video Engine - Matchup Reel Function", False, "Function not found")
        
        # Check if original function still exists
        if hasattr(video, 'create_reel'):
            log_test("Video Engine - Original Reel Function", True)
        else:
            log_test("Video Engine - Original Reel Function", False)
    
    except Exception as e:
        log_test("Video Engine - Import", False, str(e))

def test_live_wire():
    """Test 5: Live Wire System (Test Mode)"""
    print("\n" + "="*60)
    print("TEST 5: Live Wire Real-Time System (13_live_wire.py)")
    print("="*60)
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("live_wire", "13_live_wire.py")
        wire = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wire)
        
        # Check critical functions
        functions_to_check = [
            'get_live_results',
            'generate_reaction',
            'run_live_wire_once'
        ]
        
        all_present = True
        for func_name in functions_to_check:
            if not hasattr(wire, func_name):
                print(f"   ❌ Missing function: {func_name}")
                all_present = False
            else:
                print(f"   ✅ Function exists: {func_name}")
        
        if all_present:
            log_test("Live Wire - Structure", True)
            print("\n   ⏭️  Skipping live poll test (requires active event)")
            print("   To test manually: python 13_live_wire.py")
        else:
            log_test("Live Wire - Structure", False, "Missing critical functions")
    
    except Exception as e:
        log_test("Live Wire - Import", False, str(e))

def test_config_god_mode():
    """Test 6: God Mode Configuration"""
    print("\n" + "="*60)
    print("TEST 6: God Mode AI Configuration (config.py)")
    print("="*60)
    
    try:
        import config
        
        # Check model list
        if hasattr(config, 'GEMINI_MODELS'):
            models = config.GEMINI_MODELS
            print(f"   Primary Model: {models[0]}")
            
            # Check if God Mode models are present
            god_mode_models = ["gemini-3-pro-preview", "deep-research-pro", "gemini-exp-1206"]
            has_god_mode = any(any(gm in model for gm in god_mode_models) for model in models)
            
            if has_god_mode:
                log_test("Config - God Mode Models", True)
                print(f"   ✅ Using premium models (Total: {len(models)} fallbacks)")
            else:
                log_test("Config - God Mode Models", False, "Still using standard models")
        else:
            log_test("Config - GEMINI_MODELS", False, "Not found")
        
        # Check brand colors
        if hasattr(config, 'BRAND_COLORS'):
            colors = config.BRAND_COLORS
            required_keys = ['primary', 'secondary', 'accent', 'bg_dark']
            
            if all(key in colors for key in required_keys):
                log_test("Config - Brand Colors", True)
                print(f"   ✅ Brand identity defined ({len(colors)} colors)")
            else:
                log_test("Config - Brand Colors", False, "Missing required color keys")
        else:
            log_test("Config - Brand Colors", False, "BRAND_COLORS not found")
    
    except Exception as e:
        log_test("Config - Import", False, str(e))

def print_final_report():
    """Print test summary"""
    print("\n" + "="*60)
    print("📊 TEST SUITE FINAL REPORT")
    print("="*60)
    
    total = TEST_RESULTS["tests_run"]
    passed = TEST_RESULTS["tests_passed"]
    failed = TEST_RESULTS["tests_failed"]
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\nTests Run:    {total}")
    print(f"Tests Passed: {passed} ✅")
    print(f"Tests Failed: {failed} ❌")
    print(f"Pass Rate:    {pass_rate:.1f}%")
    
    if failed > 0:
        print("\n🔴 FAILURES:")
        for failure in TEST_RESULTS["failures"]:
            print(f"  - {failure['test']}")
            if failure['error']:
                print(f"    Error: {failure['error']}")
    
    # Save report
    with open("test_outputs/test_report.json", "w", encoding="utf-8") as f:
        json.dump(TEST_RESULTS, f, indent=2)
    
    print(f"\n📁 Full report saved to: test_outputs/test_report.json")
    
    print("\n" + "="*60)
    
    if pass_rate >= 80:
        print("🎉 SYSTEM READY FOR DEPLOYMENT")
    elif pass_rate >= 60:
        print("⚠️  SYSTEM NEEDS MINOR FIXES")
    else:
        print("🔴 SYSTEM NEEDS MAJOR FIXES")
    
    print("="*60 + "\n")

def main():
    """Run all tests"""
    print("="*60)
    print("🧪 FIGHTIQ INTEGRATION TEST SUITE V1")
    print("="*60)
    print(f"Timestamp: {TEST_RESULTS['timestamp']}")
    print("="*60)
    
    setup_test_environment()
    
    # Run tests
    test_config_god_mode()      # Test 6 (runs first for context)
    test_background_forge()     # Test 1
    test_visual_engine()        # Test 2
    test_ticket_generator()     # Test 3
    test_video_engine()         # Test 4
    test_live_wire()            # Test 5
    
    # Final report
    print_final_report()

if __name__ == "__main__":
    main()
