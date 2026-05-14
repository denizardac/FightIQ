import subprocess
import time
import sys
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ==========================================
# 🥊 FIGHTIQ: SYSTEM ORCHESTRATOR V2.2
# Sequential data pipeline + Structured Logging + Discord Alerts
# ==========================================

# Get project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# ==========================================
# STRUCTURED LOGGING SETUP
# ==========================================

def setup_logging():
    """Configure structured logging with rotation"""
    # Create logs directory if missing
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Define log file path
    log_file = os.path.join(LOGS_DIR, "fightiq.log")
    
    # Configure root logger
    logger = logging.getLogger("FightIQ")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Define format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler (Rotating, Max 10MB, 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler (keep visual output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==========================================
# MODULE EXECUTION
# ==========================================

def run_module(script_name):
    """Run a module from the modules directory"""
    logger.info(f"="*60)
    logger.info(f"LAUNCHING: {script_name}")
    logger.info(f"="*60)
    
    # Build full path to module
    module_path = os.path.join(MODULES_DIR, f"_{script_name}")
    
    if not os.path.exists(module_path):
        # Try without underscore prefix (legacy compatibility)
        module_path = os.path.join(PROJECT_ROOT, script_name)
    
    if not os.path.exists(module_path):
        logger.error(f"Module not found: {script_name}")
        return False
    
    start = time.time()
    # Run from project root for relative path compatibility
    result = subprocess.run(
        [sys.executable, module_path], 
        capture_output=False,
        cwd=PROJECT_ROOT
    )
    duration = round(time.time() - start, 2)
    
    if result.returncode == 0:
        logger.info(f"SUCCESS: {script_name} completed in {duration}s")
        # Track in pipeline report
        PIPELINE_REPORT["modules"][script_name] = {
            "status": "SUCCESS",
            "duration_seconds": duration,
            "exit_code": 0
        }
        return True
    else:
        logger.error(f"FAILURE: {script_name} crashed (Code {result.returncode})")
        # Track in pipeline report
        PIPELINE_REPORT["modules"][script_name] = {
            "status": "FAILED",
            "error": f"Exit code {result.returncode}",
            "duration_seconds": duration,
            "exit_code": result.returncode
        }
        return False

# ==========================================
# SYSTEM STATUS CHECKS
# ==========================================

def check_status():
    """Read system status from data/1_card.json"""
    try:
        card_path = os.path.join(DATA_DIR, "1_card.json")
        # Also check root for legacy compatibility
        if not os.path.exists(card_path):
            card_path = os.path.join(PROJECT_ROOT, "1_card.json")
        
        with open(card_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            return data.get("status", "IDLE")
    except Exception as e:
        logger.warning(f"Could not read status: {e}")
        return "IDLE"

def check_database():
    """Check if fighters database exists"""
    db_path = os.path.join(DATA_DIR, "fighters_db.json")
    # Also check root for legacy compatibility
    if not os.path.exists(db_path):
        db_path = os.path.join(PROJECT_ROOT, "fighters_db.json")
    return os.path.exists(db_path)

# ==========================================
# PIPELINE REPORT (Error Aggregation)
# ==========================================

PIPELINE_REPORT = {
    "timestamp": None,
    "mode": None,
    "modules": {},
    "summary": {
        "total": 0,
        "success": 0,
        "failed": 0,
        "warnings": 0
    }
}

def save_pipeline_report():
    """P0 FIX: Save pipeline execution report for error aggregation"""
    report_path = os.path.join(DATA_DIR, "pipeline_report.json")
    
    # Calculate summary
    PIPELINE_REPORT["summary"]["total"] = len(PIPELINE_REPORT["modules"])
    PIPELINE_REPORT["summary"]["success"] = sum(1 for m in PIPELINE_REPORT["modules"].values() if m["status"] == "SUCCESS")
    PIPELINE_REPORT["summary"]["failed"] = sum(1 for m in PIPELINE_REPORT["modules"].values() if m["status"] == "FAILED")
    PIPELINE_REPORT["summary"]["warnings"] = sum(1 for m in PIPELINE_REPORT["modules"].values() if m["status"] == "WARNING")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(PIPELINE_REPORT, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Pipeline report saved to {report_path}")
    logger.info(f"Summary: {PIPELINE_REPORT['summary']['success']}/{PIPELINE_REPORT['summary']['total']} modules succeeded")

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

def main():
    print(f"""
    ███████╗██╗ ██████╗ ██╗  ██╗████████╗██╗ ██████╗ 
    ██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝██║██╔═══██╗
    █████╗  ██║██║  ███╗███████║   ██║   ██║██║   ██║
    ██╔══╝  ██║██║   ██║██╔══██║   ██║   ██║██║▄▄ ██║
    ██║     ██║╚██████╔╝██║  ██║   ██║   ██║╚██████╔╝
    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚══▀▀═╝ 
          --- SYSTEM START: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---
          --- FIGHTIQ V2.2 (Sequential Pipeline + Logging + Alerts) ---
    """)
    
    # Initialize pipeline report
    PIPELINE_REPORT["timestamp"] = datetime.now().isoformat()
    
    logger.info("FightIQ System Orchestrator V2.2 — Sequential Pipeline")
    logger.info(f"Project Root: {PROJECT_ROOT}")
    logger.info(f"Logs Directory: {LOGS_DIR}")
    
    # 1. DATABASE CHECK
    if not check_database():
        logger.warning("Database missing. Running Indexer first...")
        if not run_module("00_indexer.py"): 
            logger.critical("Indexer failed - cannot proceed")
            PIPELINE_REPORT["mode"] = "INITIALIZATION_FAILED"
            save_pipeline_report()
            return
    
    # 2. EVENT RADAR (Determines LIVE vs IDLE)
    if not run_module("01_event_radar.py"): 
        logger.critical("Event Radar failed - cannot proceed")
        PIPELINE_REPORT["mode"] = "RADAR_FAILED"
        save_pipeline_report()
        return
    
    status = check_status()
    logger.info(f"DECISION MATRIX: System Mode is [{status}]")
    PIPELINE_REPORT["mode"] = status
    
    # 3. SCENARIO A: FIGHT WEEK (LIVE)
    if status == "LIVE":
        logger.info("MODE: WAR ROOM (Full Fight Week Analysis)")
        
        # ================================================
        # SEQUENTIAL DATA COLLECTION
        # 02 writes → 03 reads/writes → 04 reads/writes
        # These modules form a strict data chain and MUST
        # run in order — parallelism would cause race conditions.
        # ================================================
        logger.info("DATA COLLECTION PIPELINE INITIATED (sequential)")

        if not run_module("02_stat_scout.py"):
            logger.critical("Stat Scout failed - cannot proceed")
            save_pipeline_report()
            return

        if not run_module("03_odds_hunter.py"):
            logger.warning("Odds Hunter failed - continuing without live odds")

        if not run_module("04_deep_dive.py"):
            logger.critical("Deep Dive failed - cannot proceed")
            save_pipeline_report()
            return

        logger.info("Data collection complete.")
        
        # AI & PRODUCTION PIPELINE (Sequential)
        logger.info("Starting AI Analysis & Production Pipeline (sequential)")
        
        if not run_module("05_fight_brain.py"): 
            logger.critical("Fight Brain (AI Analysis) failed")
            save_pipeline_report()
            return
        
        # Prefetch fighter portraits from multiple sources before visual gen
        try:
            logger.info("Pre-fetching fighter portraits (parallel multi-source)")
            from tools.prefetch_fighter_images import main as prefetch_main
            prefetch_main()
        except Exception as e:
            logger.warning(f"Portrait prefetch had issues (continuing): {e}")
        
        if not run_module("06_visual_engine.py"): 
            logger.error("Visual Engine failed")
            save_pipeline_report()
            return
        
        # Video generation disabled — videos not posted to Twitter.
        # Run manually for TikTok/IG export when needed:
        #   python modules/_10_matchup_video_bridge.py
        # if not run_module("10_matchup_video_bridge.py"):
        #     logger.warning("Video generation failed - continuing without videos")
        
        if not run_module("07_parlay_maker.py"): 
            logger.error("Parlay Maker failed")
            save_pipeline_report()
            return
        
        if not run_module("06b_ticket_generator.py"):
            logger.warning("Ticket Generator failed - continuing without visual tickets")
        
        # PUBLISHING PIPELINE
        logger.info("Starting Publishing Pipeline")
        run_module("08_social_director.py")
    
    # 4. SCENARIO B: IDLE MODE (CONTENT GENERATION)
    else:
        logger.info("MODE: CONTENT STUDIO (Spotlight Generation)")
        if run_module("09_spotlight_engine.py"):
            run_module("08_social_director.py")
        else:
            logger.error("Spotlight Engine failed")
    
    # ── LIVE WIRE ─────────────────────────────────────────────
    # Managed exclusively via cron (deploy.sh --setup-cron):
    #   Sat 20:00 UTC + Sun 20:00 UTC
    # Do NOT spawn from here — would create duplicate processes
    # when both cron and daily pipeline run on fight night.

    logger.info("="*60)
    logger.info("💤 SYSTEM SLEEPING. Next cycle scheduled via Cronjob.")
    logger.info("="*60)
    
    # P0 FIX: Save pipeline report before exit
    save_pipeline_report()

import traceback

# P0: Import Notifier
try:
    from core.notifier import send_discord_alert
except ImportError:
    logger.warning("Notifier module not found. Alerts disabled.")
    send_discord_alert = None

if __name__ == "__main__":
    try:
        main()
        
        # Scenario B: Success Alert (End of Pipeline)
        if send_discord_alert and PIPELINE_REPORT["summary"]["total"] > 0:
            succ = PIPELINE_REPORT["summary"]["success"]
            total = PIPELINE_REPORT["summary"]["total"]
            fail = PIPELINE_REPORT["summary"]["failed"]
            mode = PIPELINE_REPORT.get("mode", "UNKNOWN")
            
            msg = f"**Pipeline Analysis Complete**\nMode: `{mode}`\nStats: {succ}/{total} Modules OK"
            status = "SUCCESS"
            
            if fail > 0:
                msg += f"\n⚠️ **Failures Detected:** {fail}"
                status = "WARNING"
                
            send_discord_alert(msg, status=status)
            
    except Exception as e:
        # Scenario A: Crash Alert
        logger.critical(f"FATAL SYSTEM CRASH: {e}")
        traceback.print_exc()
        
        if send_discord_alert:
            tb = traceback.format_exc()
            # Truncate traceback to fit Discord limit
            err_msg = f"**CRITICAL SYSTEM FAILURE**\nError: `{str(e)}`\n\nStack Trace:\n```python\n{tb[-1000:]}```"
            send_discord_alert(err_msg, status="ERROR")
        
        sys.exit(1)