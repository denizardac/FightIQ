# FightIQ — Architecture Reference

## Module Map

```
FightIQ/
├── run.py                        # Canonical entry point → calls core/main.py
├── core/
│   ├── main.py                   # Pipeline orchestrator (V2.2) — FIGHT WEEK + IDLE routing
│   ├── config.py                 # All thresholds, model names, brand colors, font paths
│   ├── paths.py                  # Centralized path resolver (use this, not os.path.join)
│   ├── notifier.py               # Discord webhook alerts
│   └── odds_converter.py         # Decimal ↔ American odds format converter
├── modules/
│   ├── _00_indexer.py            # Rebuilds fighters_db.json from UFCStats (run once)
│   ├── _01_event_radar.py        # Scrapes upcoming events; sets LIVE or IDLE in 1_card.json
│   ├── _02_stat_scout.py         # Fighter stats + news enrichment → 2_data.json
│   ├── _03_odds_hunter.py        # ⚠️ Fragile: Betist (primary) + BFO (secondary) odds
│   ├── _04_deep_dive.py          # KO/sub rates, fight history → 2_data_final.json
│   ├── _05_fight_brain.py        # Gemini AI predictions → 3_results.json
│   ├── _06_visual_engine.py      # Stat cards + radar charts → output/visuals/
│   ├── _06b_ticket_generator.py  # Imagen API betting ticket images → Ticket_*.png
│   ├── _07_parlay_maker.py       # Builds safe/violence/value slips → 4_parlays.json
│   ├── _08_social_director.py    # Twitter/X publishing (supports --dry-run flag)
│   ├── _09_spotlight_engine.py   # IDLE mode: selects fighter/mode by day of week
│   ├── _10_video_engine.py       # Core video renderer (MoviePy + Edge-TTS)
│   ├── _10_matchup_video_bridge.py # Connects 3_results.json → video engine
│   ├── _11_trend_hunter.py       # Sherdog RSS scraper for trending fighters
│   ├── _12_background_forge.py   # Imagen AI background generation + cache
│   └── _13_live_wire.py          # Fight night: polls UFC Stats, posts reactions
├── data/                         # Runtime data (gitignored except fighters_db.json)
├── output/visuals/               # Generated images + videos
├── assets/
│   ├── fonts/                    # Bebas Neue + Roboto (must be present — see assets/fonts/README.md)
│   ├── images_cache/             # Cached fighter portrait PNGs
│   └── backgrounds/              # Imagen-generated background cache
├── tools/
│   ├── check_models.py           # Lists available Gemini models via live API call
│   ├── list_models_raw.py        # Raw model list dump
│   ├── test_imports.py           # Verifies all modules import cleanly
│   ├── verify_odds.py            # Quick odds scraper sanity check
│   ├── verify_odds_scraper.py    # Full Betist + BFO scraper validation
│   ├── test_odds_sources.py      # Tests both odds sources independently
│   ├── debug_betist_live.py      # Live Betist API debug/inspection
│   ├── debug_odds_deep_scan.py   # Deep scan of BFO odds pages
│   ├── test_complete_extraction.py # End-to-end odds extraction test
│   ├── simple_odds_test.py       # Minimal odds connectivity test
│   └── test_imagen.py            # Imagen API connectivity test
└── tests/
    ├── simulate_week.py          # Generates mock week of IDLE content
    ├── test_idle_modes.py        # Validates day→mode mapping
    ├── test_full_cycle.py        # Integration test (no API calls)
    ├── test_creative_modes.py    # Validates all 5 creative content modes
    ├── test_live_odds_connection.py # Validates live odds scraper connectivity
    ├── test_notifier.py          # Discord notifier unit test
    └── debug_bfo_detail_page.py  # BestFightOdds detail page scraper debug
```

---

## Data Flow (FIGHT WEEK)

```
UFCStats.com → [01_event_radar] → 1_card.json
                                        ↓
               ┌────────────── PARALLEL ──────────────┐
         [02_stat_scout]    [03_odds_hunter]    [04_deep_dive]
               └──────────────────┬──────────────────┘
                            2_data_final.json
                                  ↓
                          [05_fight_brain] ← Gemini API
                                  ↓
                            3_results.json
                           ↙             ↘
              [06_visual_engine]    [07_parlay_maker]
              [10_video_bridge]     [06b_ticket_generator]
                           ↘             ↙
                       [08_social_director]
                                  ↓
                             Twitter/X ✅
```

---

## Key Configuration (`core/config.py`)

```python
# AI Models (in priority order — confirmed working 2026-03-26)
GEMINI_MODELS = [
    "models/gemini-3.1-pro-preview",   # PRIMARY (God Mode)
    "models/gemini-2.5-pro",           # SECONDARY
    "models/gemini-2.5-flash",         # TERTIARY
    "models/gemini-2.0-flash",         # QUATERNARY
    "models/gemini-2.0-flash-lite",    # ULTIMATE FALLBACK
]

# Image Generation
IMAGEN_MODEL = "models/imagen-4.0-generate-preview-06-06"

# Parlay thresholds
PARLAY_SAFE_CONFIDENCE = 8    # Min AI confidence score (0-10)
PARLAY_VIOLENCE_SCORE = 80    # Min violence score (0-100)

# Odds scraper
BETIST_REDIRECT_URL = "https://cutt.ly/zrIT6E9d"  # Update if Betist changes domain

# Brand colors
BRAND_COLORS = {"primary": "#00FF41", "secondary": "#FFD700", "accent": "#FF0055", ...}

# Font paths (relative to PROJECT_ROOT)
FONT_PATHS = {
    "headline": "assets/fonts/BebasNeue-Regular.ttf",
    "body_bold": "assets/fonts/Roboto-Bold.ttf",
    "body_regular": "assets/fonts/Roboto-Regular.ttf"
}
```

---

## Adding a New Module

1. Create `modules/_14_your_module.py`
2. Add `sys.path.append(...)` + `from core.paths import ...` at top
3. Add a `main()` function as entry point
4. Insert the call in `core/main.py` at the right pipeline stage
5. Run `python tools/test_imports.py` to verify it imports cleanly
