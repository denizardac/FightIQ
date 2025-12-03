import subprocess
import time
import sys
import os

# --- FIGHTIQ: AUTONOMOUS MMA ANALYSIS PIPELINE ---

def run_step(script_name, description):
    print(f"\n" + "="*60)
    print(f"🚀 STARTING MODULE: {description}")
    print(f"   📄 Script: {script_name}")
    print("="*60)
    
    start_time = time.time()
    
    # Python scriptini çalıştır
    # sys.executable, o an kullanılan python.exe'yi garanti eder (Virtualenv dostu)
    result = subprocess.run([sys.executable, script_name], capture_output=False)
    
    duration = round(time.time() - start_time, 2)
    
    if result.returncode == 0:
        print(f"\n✅ MODULE COMPLETE: {script_name} finished in {duration}s.")
        return True
    else:
        print(f"\n❌ MODULE FAILED: {script_name} crashed (Code {result.returncode}).")
        return False

def main():
    print("""
    ███████╗██╗ ██████╗ ██╗  ██╗████████╗██╗ ██████╗ 
    ██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝██║██╔═══██╗
    █████╗  ██║██║  ███╗███████║   ██║   ██║██║   ██║
    ██╔══╝  ██║██║   ██║██╔══██║   ██║   ██║██║▄▄ ██║
    ██║     ██║╚██████╔╝██║  ██║   ██║   ██║╚██████╔╝
    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚══▀▀═╝ 
          --- FIGHTIQ AUTONOMOUS SYSTEM v1.0 ---
    """)
    
    # ADIM 0: Veritabanı Kontrolü (Yoksa oluşturur)
    if not os.path.exists("fighters_db.json"):
        print("⚠️ Fighter Database not found. Initializing Indexer...")
        if not run_step("00_indexer.py", "Database Generator"): return
    else:
        print("📚 Database Check: OK (fighters_db.json exists)")

    # ADIM 1: Etkinlik Bulucu
    if not run_step("01_event_radar.py", "Event Radar (UFCStats)"): return
    
    # ADIM 2: İstatistik Toplayıcı
    if not run_step("02_stat_scout.py", "Stat Scout (Basic Data)"): return
    
    # ADIM 3: Oran Avcısı (Betist API)
    if not run_step("03_odds_hunter.py", "Odds Hunter (Betist API)"): return
    
    # ADIM 4: Derin Analiz (UFCStats Deep Dive)
    if not run_step("04_deep_dive.py", "Deep Dive Engine (Advanced Stats)"): return
    
    # ADIM 5: Yapay Zeka Beyni (Gemini)
    if os.path.exists("05_fight_brain.py"):
        if not run_step("05_fight_brain.py", "FightIQ AI Brain"): return
    else:
        print("\n🚧 WAITING: '05_fight_brain.py' not found (Next Step).")

    print("\n" + "="*60)
    print("🎉 PIPELINE FINISHED SUCCESSFULLY. CHECK '3_results.json'")
    print("="*60)

if __name__ == "__main__":
    main()