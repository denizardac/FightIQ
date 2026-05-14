"""
FightIQ Full System Simulation
Runs each IDLE mode (Mon-Fri) and each LIVE pipeline step,
reports expected vs actual output with pass/fail status.

Usage:
    python tests/run_simulation.py --idle      # Run all 5 IDLE modes
    python tests/run_simulation.py --live      # Run LIVE pipeline steps
    python tests/run_simulation.py --all       # Run everything
    python tests/run_simulation.py --mode ORACLE   # Run single IDLE mode
"""

import sys
import os
import subprocess
import json
import time
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
from core.paths import get_data_path, get_output_path, VISUALS_DIR, DATA_DIR

# ─────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}[PASS]{RESET}  {msg}")
def fail(msg):  print(f"  {RED}[FAIL]{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}[WARN]{RESET}  {msg}")
def info(msg):  print(f"  {CYAN}[INFO]{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{'='*60}\n  {msg}\n{'='*60}{RESET}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def run_module(rel_path, timeout=180, extra_args=None):
    """Run a module, return (returncode, stdout, elapsed_seconds)."""
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, rel_path)]
    if extra_args:
        cmd += extra_args
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        elapsed = round(time.time() - start, 1)
        return result.returncode, result.stdout + result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start, 1)
        return -1, f"TIMEOUT after {elapsed}s", elapsed

def check_file(path, min_bytes=100):
    """Return (exists, size_bytes)."""
    if os.path.exists(path):
        sz = os.path.getsize(path)
        return sz >= min_bytes, sz
    return False, 0

def check_json(path, required_keys=None):
    """Return (valid, data_or_error)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if required_keys:
            missing = [k for k in required_keys if k not in data]
            if missing:
                return False, f"Missing keys: {missing}"
        return True, data
    except Exception as e:
        return False, str(e)

def check_visuals(pattern_prefix, min_count=1):
    """Count files in VISUALS_DIR matching a prefix."""
    if not os.path.exists(VISUALS_DIR):
        return 0
    files = [f for f in os.listdir(VISUALS_DIR) if f.startswith(pattern_prefix)]
    return len(files)

# ─────────────────────────────────────────────
# IDLE MODE DEFINITIONS
# ─────────────────────────────────────────────

IDLE_MODES = [
    {
        "day": "Monday",
        "mode": "STANDARD",
        "description": "Fighter profile hype post — single fighter, stat card, video",
        "expected_outputs": [
            {"label": "spotlight_ready.json",        "path": get_data_path("spotlight_ready.json"),      "keys": ["fighter","thread"]},
            {"label": "Card_*.png in visuals/",       "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Reel_*.mp4 in visuals/",       "type": "visual_prefix", "prefix": "Reel_"},
        ],
        "expected_twitter": "1 main tweet + 1 stat reply (text-only or with card image)",
    },
    {
        "day": "Tuesday",
        "mode": "ORACLE",
        "description": "Fantasy matchup post — two fighters, versus card, poll",
        "expected_outputs": [
            {"label": "spotlight_ready.json",         "path": get_data_path("spotlight_ready.json"),      "keys": ["fighter","thread"]},
            {"label": "Card_*.png in visuals/",       "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Reel_*.mp4 in visuals/",       "type": "visual_prefix", "prefix": "Reel_"},
        ],
        "expected_twitter": "Main tweet + poll (Team A vs Team B) + optional versus card",
    },
    {
        "day": "Wednesday",
        "mode": "VIOLENCE",
        "description": "High-finisher hype — fighter with top SLpM, violence framing",
        "expected_outputs": [
            {"label": "spotlight_ready.json",         "path": get_data_path("spotlight_ready.json"),      "keys": ["fighter","thread"]},
            {"label": "Card_*.png in visuals/",       "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Reel_*.mp4 in visuals/",       "type": "visual_prefix", "prefix": "Reel_"},
        ],
        "expected_twitter": "Aggressive tweet + stat reply + card image",
    },
    {
        "day": "Thursday",
        "mode": "HISTORY",
        "description": "Veteran throwback — fighter with 20+ wins, legacy framing",
        "expected_outputs": [
            {"label": "spotlight_ready.json",         "path": get_data_path("spotlight_ready.json"),      "keys": ["fighter","thread"]},
            {"label": "Card_*.png in visuals/",       "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Reel_*.mp4 in visuals/",       "type": "visual_prefix", "prefix": "Reel_"},
        ],
        "expected_twitter": "Legacy/throwback tweet + stat reply + card",
    },
    {
        "day": "Friday",
        "mode": "ANOMALY",
        "description": "Betting value alert — underdog or stat-gap fighter",
        "expected_outputs": [
            {"label": "spotlight_ready.json",         "path": get_data_path("spotlight_ready.json"),      "keys": ["fighter","thread"]},
            {"label": "Card_*.png in visuals/",       "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Reel_*.mp4 in visuals/",       "type": "visual_prefix", "prefix": "Reel_"},
        ],
        "expected_twitter": "Wolf-ticket / value alert tweet + odds/stat note",
    },
]

# ─────────────────────────────────────────────
# LIVE PIPELINE STEP DEFINITIONS
# ─────────────────────────────────────────────

LIVE_STEPS = [
    {
        "step": "01",
        "name": "Event Radar",
        "module": "modules/_01_event_radar.py",
        "description": "Scrape UFCStats for next event, set LIVE/IDLE status",
        "expected_outputs": [
            {"label": "data/1_card.json", "path": get_data_path("1_card.json"), "keys": ["event","status","fights"]},
        ],
        "critical": True,
        "timeout": 30,
    },
    {
        "step": "02",
        "name": "Stat Scout",
        "module": "modules/_02_stat_scout.py",
        "description": "Scrape fighter stats + news for each fight on the card",
        "expected_outputs": [
            {"label": "data/2_data.json",  "path": get_data_path("2_data.json"), "keys": None},
        ],
        "critical": True,
        "timeout": 240,
    },
    {
        "step": "03",
        "name": "Odds Hunter",
        "module": "modules/_03_odds_hunter.py",
        "description": "Fetch live odds from Betist (primary) + BFO (secondary)",
        "expected_outputs": [
            {"label": "data/2_data_with_odds.json", "path": get_data_path("2_data_with_odds.json"), "keys": None},
        ],
        "critical": False,
        "timeout": 120,
    },
    {
        "step": "04",
        "name": "Deep Dive",
        "module": "modules/_04_deep_dive.py",
        "description": "Enrich with KO/sub rates and fight history from UFCStats",
        "expected_outputs": [
            {"label": "data/2_data_final.json", "path": get_data_path("2_data_final.json"), "keys": None},
        ],
        "critical": True,
        "timeout": 240,
    },
    {
        "step": "05",
        "name": "Fight Brain (AI)",
        "module": "modules/_05_fight_brain.py",
        "description": "Gemini AI generates predictions + analysis for every fight",
        "expected_outputs": [
            {"label": "data/3_results.json", "path": get_data_path("3_results.json"), "keys": None},
        ],
        "critical": True,
        "timeout": 600,
    },
    {
        "step": "06",
        "name": "Visual Engine",
        "module": "modules/_06_visual_engine.py",
        "description": "Generate stat cards (PNG) and radar charts for each fight",
        "expected_outputs": [
            {"label": "Card_*.png files in output/visuals/",  "type": "visual_prefix", "prefix": "Card_"},
            {"label": "Radar_*.png files in output/visuals/", "type": "visual_prefix", "prefix": "Radar_"},
        ],
        "critical": True,
        "timeout": 120,
    },
    {
        "step": "10",
        "name": "Video Bridge",
        "module": "modules/_10_matchup_video_bridge.py",
        "description": "Create MP4 matchup reels from radar charts + TTS voiceover",
        "expected_outputs": [
            {"label": "Reel_Matchup_*.mp4 in output/visuals/", "type": "visual_prefix", "prefix": "Reel_Matchup_"},
        ],
        "critical": False,
        "timeout": 600,
    },
    {
        "step": "07",
        "name": "Parlay Maker",
        "module": "modules/_07_parlay_maker.py",
        "description": "Build safe / violence / value betting slips",
        "expected_outputs": [
            {"label": "data/4_parlays.json", "path": get_data_path("4_parlays.json"),
             "keys": ["safe_slip", "violence_slip", "value_slip"]},
        ],
        "critical": True,
        "timeout": 30,
    },
    {
        "step": "06b",
        "name": "Ticket Generator",
        "module": "modules/_06b_ticket_generator.py",
        "description": "Create Imagen AI betting ticket images (Ticket_Safe/Violence/Value.png)",
        "expected_outputs": [
            {"label": "Ticket_Safe.png",     "type": "visual_file", "file": "Ticket_Safe.png"},
            {"label": "Ticket_Violence.png", "type": "visual_file", "file": "Ticket_Violence.png"},
            {"label": "Ticket_Value.png",    "type": "visual_file", "file": "Ticket_Value.png"},
        ],
        "critical": False,
        "timeout": 120,
    },
    {
        "step": "08",
        "name": "Social Director (DRY RUN)",
        "module": "modules/_08_social_director.py",
        "description": "Publish to Twitter/X — DRY RUN mode (no actual posts)",
        "expected_outputs": [],
        "critical": False,
        "timeout": 120,
        "extra_args": ["--dry-run"],
    },
]

# ─────────────────────────────────────────────
# SIMULATION RUNNERS
# ─────────────────────────────────────────────

def simulate_idle_mode(mode_def):
    day = mode_def["day"]
    mode = mode_def["mode"]
    header(f"IDLE — {day.upper()} ({mode})")
    print(f"  {mode_def['description']}")
    print(f"  Expected Twitter: {mode_def['expected_twitter']}\n")

    rc, output, elapsed = run_module(
        "modules/_09_spotlight_engine.py",
        timeout=300,
        extra_args=["--mode", mode]
    )

    print(f"  Exit code: {rc} | Time: {elapsed}s")

    results = {"mode": mode, "day": day, "elapsed": elapsed, "pass": [], "fail": [], "warn": []}

    if rc == -1:
        fail(f"TIMEOUT after {elapsed}s — module hung")
        results["fail"].append("TIMEOUT")
    elif rc != 0:
        fail(f"Module exited with code {rc}")
        results["fail"].append(f"exit_code={rc}")
    else:
        ok(f"Module completed in {elapsed}s")

    # Check stdout for known error patterns
    if "FATAL" in output.upper():
        fail("FATAL error in output")
        results["fail"].append("FATAL in stdout")
    if "DONE!" in output or "spotlight_ready.json created" in output:
        ok("spotlight_ready.json written")
    elif rc == 0:
        warn("No confirmation message found in output")
        results["warn"].append("no confirmation")

    # Check expected output files
    for exp in mode_def["expected_outputs"]:
        if exp.get("type") == "visual_prefix":
            count = check_visuals(exp["prefix"])
            if count > 0:
                ok(f"{exp['label']}: {count} file(s) found")
                results["pass"].append(exp["label"])
            else:
                warn(f"{exp['label']}: 0 files (may be new mode / first run)")
                results["warn"].append(exp["label"])
        else:
            exists, sz = check_file(exp["path"])
            if exists:
                valid, data = check_json(exp["path"], exp.get("keys"))
                if valid:
                    fighter = data.get("fighter", "?") if isinstance(data, dict) else "?"
                    thread_count = len(data.get("thread", [])) if isinstance(data, dict) else 0
                    ok(f"{exp['label']}: OK ({sz:,} bytes) — fighter={fighter}, tweets={thread_count}")
                    results["pass"].append(exp["label"])
                else:
                    fail(f"{exp['label']}: JSON invalid — {data}")
                    results["fail"].append(exp["label"])
            else:
                fail(f"{exp['label']}: NOT FOUND")
                results["fail"].append(exp["label"])

    # Print AI content preview
    sr_path = get_data_path("spotlight_ready.json")
    sr_valid, sr_data = check_json(sr_path)
    if sr_valid and isinstance(sr_data, dict):
        thread = sr_data.get("thread", [])
        if thread:
            print(f"\n  {CYAN}[CONTENT PREVIEW — Tweet 1]{RESET}")
            print(f"  {thread[0][:120]}...")
            if len(thread) > 1:
                print(f"  {CYAN}[Tweet 2]{RESET} {thread[1][:100]}...")

    # Summary line
    p, f_, w = len(results["pass"]), len(results["fail"]), len(results["warn"])
    status = f"{GREEN}PASS{RESET}" if f_ == 0 else f"{RED}FAIL{RESET}"
    print(f"\n  Result: {status} | Checks: {p} passed, {f_} failed, {w} warnings")

    # Print last lines of stdout if there was an error
    if rc != 0 or "FATAL" in output.upper():
        print(f"\n  {YELLOW}--- Last output lines ---{RESET}")
        for line in output.strip().split("\n")[-15:]:
            print(f"  {line}")

    return results


def simulate_live_step(step_def):
    step = step_def["step"]
    name = step_def["name"]
    header(f"LIVE — STEP {step}: {name}")
    print(f"  {step_def['description']}")
    critical_label = f"{RED}[CRITICAL]{RESET}" if step_def["critical"] else f"{YELLOW}[NON-CRITICAL]{RESET}"
    print(f"  Criticality: {critical_label}\n")

    extra = step_def.get("extra_args")
    rc, output, elapsed = run_module(
        step_def["module"],
        timeout=step_def["timeout"],
        extra_args=extra
    )

    print(f"  Exit code: {rc} | Time: {elapsed}s")

    results = {"step": step, "name": name, "elapsed": elapsed, "pass": [], "fail": [], "warn": []}

    if rc == -1:
        msg = f"TIMEOUT after {elapsed}s"
        if step_def["critical"]:
            fail(msg)
            results["fail"].append("TIMEOUT")
        else:
            warn(msg)
            results["warn"].append("TIMEOUT")
    elif rc != 0:
        msg = f"Exit code {rc}"
        if step_def["critical"]:
            fail(msg)
            results["fail"].append(msg)
        else:
            warn(msg)
            results["warn"].append(msg)
    else:
        ok(f"Completed in {elapsed}s")
        results["pass"].append("exit_ok")

    # Check expected outputs
    for exp in step_def["expected_outputs"]:
        if exp.get("type") == "visual_prefix":
            count = check_visuals(exp["prefix"])
            if count > 0:
                ok(f"{exp['label']}: {count} file(s) found")
                results["pass"].append(exp["label"])
            else:
                fail(f"{exp['label']}: 0 files — visual generation failed")
                results["fail"].append(exp["label"])
        elif exp.get("type") == "visual_file":
            fp = os.path.join(VISUALS_DIR, exp["file"])
            exists, sz = check_file(fp, min_bytes=10000)
            if exists:
                ok(f"{exp['label']}: {sz:,} bytes")
                results["pass"].append(exp["label"])
            else:
                warn(f"{exp['label']}: not found (Imagen API may have failed)")
                results["warn"].append(exp["label"])
        elif "path" in exp:
            exists, sz = check_file(exp["path"])
            if exists:
                valid, data = check_json(exp["path"], exp.get("keys"))
                if valid:
                    if isinstance(data, dict):
                        fights = data.get("fights", [])
                        info_str = f"{sz:,} bytes"
                        if fights:
                            info_str += f", {len(fights)} fights"
                        ok(f"{exp['label']}: OK ({info_str})")
                    elif isinstance(data, list):
                        ok(f"{exp['label']}: OK ({sz:,} bytes, {len(data)} items)")
                    else:
                        ok(f"{exp['label']}: OK ({sz:,} bytes)")
                    results["pass"].append(exp["label"])
                else:
                    fail(f"{exp['label']}: JSON invalid — {data}")
                    results["fail"].append(exp["label"])
            else:
                if step_def["critical"]:
                    fail(f"{exp['label']}: NOT FOUND")
                    results["fail"].append(exp["label"])
                else:
                    warn(f"{exp['label']}: not found (non-critical)")
                    results["warn"].append(exp["label"])

    # Special post-step checks
    if step == "01":
        sr_path = get_data_path("1_card.json")
        valid, data = check_json(sr_path)
        if valid and isinstance(data, dict):
            status = data.get("status", "?")
            event = data.get("event", "?")
            days = data.get("days_until", "?")
            fights_count = len(data.get("fights", []))
            color = GREEN if status == "LIVE" else CYAN
            info(f"Mode: {color}{status}{RESET} | Event: {event} | Days: {days} | Fights: {fights_count}")

    if step == "05":
        sr_path = get_data_path("3_results.json")
        valid, data = check_json(sr_path)
        if valid and isinstance(data, list) and data:
            first = data[0]
            matchup = first.get("matchup", "?")
            brain = first.get("fight_brain_output", {})
            pred = brain.get("prediction", {})
            winner = pred.get("winner", "?")
            conf = pred.get("confidence", "?")
            method = pred.get("method", "?")
            info(f"Sample prediction: {matchup} → {winner} ({method}, confidence={conf})")

    if step == "07":
        sr_path = get_data_path("4_parlays.json")
        valid, data = check_json(sr_path)
        if valid and isinstance(data, dict):
            safe = len(data.get("safe_slip", []))
            viol = len(data.get("violence_slip", []))
            val = len(data.get("value_slip", []))
            info(f"Parlays: {safe} safe picks, {viol} violence picks, {val} value picks")

    if step == "08":
        # DRY RUN — check output mentions it
        if "DRY-RUN" in output.upper() or "dry" in output.lower():
            ok("Dry-run mode confirmed — no posts sent")
            results["pass"].append("dry_run_confirmed")
        else:
            warn("No dry-run confirmation in output")

    # Show last lines if failure
    p, f_, w = len(results["pass"]), len(results["fail"]), len(results["warn"])
    status_label = f"{GREEN}PASS{RESET}" if f_ == 0 else f"{RED}FAIL{RESET}"
    print(f"\n  Result: {status_label} | Checks: {p} passed, {f_} failed, {w} warnings")

    if rc != 0 or results["fail"]:
        print(f"\n  {YELLOW}--- Last output lines ---{RESET}")
        for line in output.strip().split("\n")[-20:]:
            print(f"  {line}")

    return results


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def print_summary(all_results, mode_label):
    header(f"SUMMARY — {mode_label}")
    total_pass = total_fail = total_warn = 0
    for r in all_results:
        p = len(r.get("pass", []))
        f_ = len(r.get("fail", []))
        w = len(r.get("warn", []))
        total_pass += p; total_fail += f_; total_warn += w
        name = r.get("mode") or r.get("name", "?")
        day_or_step = r.get("day") or f"Step {r.get('step', '?')}"
        elapsed = r.get("elapsed", 0)
        status = f"{GREEN}PASS{RESET}" if f_ == 0 else f"{RED}FAIL{RESET}"
        print(f"  {status}  {day_or_step:12s}  {name:25s}  {p}P/{f_}F/{w}W  ({elapsed}s)")

    overall = f"{GREEN}ALL PASS{RESET}" if total_fail == 0 else f"{RED}HAS FAILURES{RESET}"
    print(f"\n  Overall: {overall} | Total: {total_pass} pass, {total_fail} fail, {total_warn} warn")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FightIQ System Simulation")
    parser.add_argument("--idle",   action="store_true", help="Run all 5 IDLE modes")
    parser.add_argument("--live",   action="store_true", help="Run full LIVE pipeline")
    parser.add_argument("--all",    action="store_true", help="Run both IDLE and LIVE")
    parser.add_argument("--mode",   type=str,            help="Run single IDLE mode (STANDARD/ORACLE/etc.)")
    parser.add_argument("--step",   type=str,            help="Run single LIVE step (01/02/...)")
    parser.add_argument("--from-step", type=str,         help="Run LIVE from this step onwards")
    args = parser.parse_args()

    start_time = time.time()
    print(f"\n{BOLD}FightIQ System Simulation — {datetime.now().strftime('%Y-%m-%d %H:%M')}{RESET}")

    all_idle = []
    all_live = []

    if args.mode:
        modes = [m for m in IDLE_MODES if m["mode"] == args.mode.upper()]
        if not modes:
            print(f"Unknown mode: {args.mode}")
            sys.exit(1)
        all_idle.append(simulate_idle_mode(modes[0]))

    elif args.step:
        steps = [s for s in LIVE_STEPS if s["step"] == args.step]
        if not steps:
            print(f"Unknown step: {args.step}")
            sys.exit(1)
        all_live.append(simulate_live_step(steps[0]))

    elif args.idle or args.all:
        for mode_def in IDLE_MODES:
            all_idle.append(simulate_idle_mode(mode_def))
        if all_idle:
            print_summary(all_idle, "IDLE MODES")

    if args.live or args.all:
        steps = LIVE_STEPS
        if args.from_step:
            idx = next((i for i, s in enumerate(LIVE_STEPS) if s["step"] == args.from_step), 0)
            steps = LIVE_STEPS[idx:]
        for step_def in steps:
            result = simulate_live_step(step_def)
            all_live.append(result)
            # Stop on critical failure
            if result["fail"] and step_def["critical"]:
                fail(f"\nCritical step {step_def['step']} failed — stopping LIVE pipeline")
                break
        if all_live:
            print_summary(all_live, "LIVE PIPELINE")

    total_elapsed = round(time.time() - start_time, 1)
    print(f"\n  Total simulation time: {total_elapsed}s")
