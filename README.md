# FightIQ — Project Documentation

## What Is FightIQ?
An automated MMA content pipeline that runs daily via cron. It scrapes UFC data, generates AI fight predictions using Gemini, creates visual cards and video reels, then posts everything to Twitter/X automatically.

---

## Quick Start

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys in .env (see .env.example)
GEMINI_API_KEY=...
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_SECRET=...
DISCORD_WEBHOOK_URL=...  # Optional but recommended
```

### Run Pipeline
```bash
# Recommended: use the root launcher
python run.py

# Or call core directly
python core/main.py
```
The system auto-detects mode (FIGHT WEEK or IDLE) and runs accordingly.

---

## Two Operating Modes

### 🟥 FIGHT WEEK (Auto-activates when event ≤ 6 days away)
Full AI analysis pipeline:
1. Scrapes UFC event card → `data/1_card.json`
2. Collects stats + news → `data/2_data.json`
3. Scrapes live odds (Betist + BFO) → `data/2_data_with_odds.json`
4. Deep history analysis → `data/2_data_final.json`
5. Gemini AI predictions → `data/3_results.json`
6. Generates visual cards + radar charts → `output/visuals/`
7. Creates matchup video reels (TTS) → `output/visuals/*.mp4`
8. Builds betting slips (Safe / Violence / Edge) → `data/4_parlays.json`
9. Generates ticket images (Imagen API) → `output/visuals/Ticket_*.png`
10. Posts to Twitter → Done

**Cost**: ~$2.50–4.00 per event | **Time**: ~3–5 min

### 🟦 IDLE MODE (No event within 6 days)
Daily fighter spotlight content, rotated by day of week:

| Day | Mode | Content |
|-----|------|---------|
| Monday | STANDARD | Fighter profile hype |
| Tuesday | ORACLE | Fantasy matchup + poll |
| Wednesday | VIOLENCE | Finish-rate highlighters |
| Thursday | HISTORY | Veteran throwbacks |
| Friday | ANOMALY | Betting value/stat gaps |
| Saturday | STANDARD | Fighter spotlight (IDLE) |
| Sunday | STANDARD | Fighter spotlight + stat card (IDLE) |

**Cost**: ~$0.05–0.10/day | **Time**: ~2 min

---

## Production Deployment (VPS)

### First-time setup
```bash
git clone <your-repo> FightIQ && cd FightIQ
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your API keys
cp .env.example .env
nano .env

# Build fighter database (run once, takes ~5 min)
python modules/_00_indexer.py

# Test the pipeline (dry run — no Twitter posts)
python modules/_08_social_director.py --dry-run
python run.py
```

### Deploy + cron setup (single command)
```bash
bash core/deploy.sh --setup-cron
```

This script will:
- Pull latest code from git
- Install/update dependencies
- Verify `.env` and `data/fighters_db.json`
- Install the two cron jobs below

### Cron schedule (installed automatically by deploy.sh)
```
# Daily pipeline — 09:00 every day
0 9 * * * /path/to/venv/bin/python3 /path/to/FightIQ/run.py >> logs/cron.log 2>&1

# Fight night Live Wire — 18:00 every Saturday
0 18 * * 6 /path/to/venv/bin/python3 /path/to/FightIQ/modules/_13_live_wire.py --auto >> logs/livewire.log 2>&1
```

### Pre-flight checklist
1. `.env` has all API keys (including `DISCORD_WEBHOOK_URL` for alerts)
2. `data/fighters_db.json` populated (`python modules/_00_indexer.py`)
3. `assets/fonts/` contains the 3 font files (see `assets/fonts/README.md`)
4. Dry-run test passes: `python run.py`

---

## Monitoring
- **Discord Alerts**: Set `DISCORD_WEBHOOK_URL` in `.env` to receive SUCCESS/FAILURE/CRITICAL notifications
- **Logs**: `logs/fightiq.log` (rotating, 10 MB, 5 backups)
- **Pipeline Report**: `data/pipeline_report.json` (auto-generated after each run)

---

## Manual Module Testing (SIMULATION_GUIDE)

Run steps individually for QA:
```bash
python modules/_01_event_radar.py   # Detect event, set LIVE/IDLE
python modules/_02_stat_scout.py    # Scrape fighter stats
python modules/_03_odds_hunter.py   # Fetch betting odds (may fail - non-critical)
python modules/_04_deep_dive.py     # Fight history
python modules/_05_fight_brain.py   # Gemini AI analysis
python modules/_06_visual_engine.py # Stat cards + radar charts
python modules/_10_matchup_video_bridge.py  # Video reels
python modules/_07_parlay_maker.py  # Betting slips
python modules/_06b_ticket_generator.py     # Ticket images
python modules/_08_social_director.py       # Twitter publish
python modules/_13_live_wire.py --auto      # Live fight commentary
```

---

## Force-Test Idle Mode
```bash
python modules/_09_spotlight_engine.py --mode VIOLENCE
python modules/_09_spotlight_engine.py --mode ORACLE
```
