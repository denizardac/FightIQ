import subprocess
import time
import sys
import os
import json
from datetime import datetime

# ==========================================
# 🥊 FIGHTIQ: SYSTEM ORCHESTRATOR
# ==========================================

def run_module(script_name):
    print(f"\n" + "═"*60)
    print(f"🚀 LAUNCHING: {script_name}")
    print("═"*60)
    
    start = time.time()
    # Python yorumlayıcısı ile çalıştır
    result = subprocess.run([sys.executable, script_name], capture_output=False)
    duration = round(time.time() - start, 2)
    
    if result.returncode == 0:
        print(f"✅ SUCCESS: {script_name} completed in {duration}s.")
        return True
    else:
        print(f"❌ FAILURE: {script_name} crashed (Code {result.returncode}).")
        return False

def check_status():
    """1_card.json dosyasından sistem durumunu okur"""
    try:
        with open("1_card.json", "r") as f:
            data = json.load(f)
            # Eğer status yoksa veya IDLE ise IDLE dön
            return data.get("status", "IDLE")
    except: return "IDLE"

def main():
    print(f"""
    ███████╗██╗ ██████╗ ██╗  ██╗████████╗██╗ ██████╗ 
    ██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝██║██╔═══██╗
    █████╗  ██║██║  ███╗███████║   ██║   ██║██║   ██║
    ██╔══╝  ██║██║   ██║██╔══██║   ██║   ██║██║▄▄ ██║
    ██║     ██║╚██████╔╝██║  ██║   ██║   ██║╚██████╔╝
    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚══▀▀═╝ 
          --- SYSTEM START: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---
    """)
    
    # 1. TEMEL KONTROLLER
    # Veritabanı yoksa oluştur (Sadece ilk kurulumda çalışır)
    if not os.path.exists("fighters_db.json"):
        print("⚠️ Database missing. Running Indexer first...")
        if not run_module("00_indexer.py"): return

    # 2. TAKVİM VE DURUM KONTROLÜ
    if not run_module("01_event_radar.py"): return
    
    status = check_status()
    print(f"\n📊 DECISION MATRIX: System Mode is [{status}]")
    
    # 3. SENARYO A: MAÇ HAFTASI (LIVE)
    if status == "LIVE":
        print("⚔️  MODE: WAR ROOM (Full Analysis)")
        # Veri Toplama Hattı
        if not run_module("02_stat_scout.py"): return
        if not run_module("03_odds_hunter.py"): return
        if not run_module("04_deep_dive.py"): return
        
        # Zeka ve Üretim Hattı
        if not run_module("05_fight_brain.py"): return
        if not run_module("06_visual_engine.py"): return
        if not run_module("10_matchup_video_bridge.py"): return  # NEW: Generate matchup videos
        if not run_module("07_parlay_maker.py"): return
        if not run_module("06b_ticket_generator.py"): return  # NEW: Generate betting tickets
        
        # Yayın Hattı
        run_module("08_social_director.py")
    
    # 4. SENARYO B: İÇERİK MODU (IDLE / CONTENT)
    else:
        print("🎬 MODE: CONTENT STUDIO (Spotlight Generation)")
        # Rastgele Efsane Seç ve Kartını Çiz
        if run_module("09_spotlight_engine.py"):
            # Yayınla
            run_module("08_social_director.py")

    print("\n" + "═"*60)
    print(f"💤 SYSTEM SLEEPING. Next cycle scheduled via Cronjob.")
    print("═"*60)

if __name__ == "__main__":
    main()