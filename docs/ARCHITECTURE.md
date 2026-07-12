# FightIQ — Architecture Reference

## Module Map

```
FightIQ/
├── run.py                        # Canonical entry point → calls core/main.py
├── core/
│   ├── main.py                   # Pipeline orchestrator (V2.2) — FIGHT WEEK + IDLE routing
│   ├── config.py                 # All thresholds, model names, brand colors, font paths
│   ├── paths.py                  # Centralized path resolver (use this, not os.path.join)
│   ├── naming.py                 # Canonical visual filename sanitizer (Card_/Radar_/Versus_/Reel_)
│   ├── pipeline_meta.py          # Stage stamping + stale-input guards (stamp_stage/require_fresh_stage)
│   ├── notifier.py               # Discord webhook alerts
│   ├── twitter_client.py         # Unified poster: tweepy (official) / twikit (cookies), poll support
│   ├── fighter_rating.py         # Matchup-relative bars + compute_streaks
│   ├── parlay_logic.py           # Shared slip helpers (pick matching, combined odds)
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
│   ├── _13_live_wire.py          # Fight night: polls UFC Stats, posts reactions
│   └── _14_scorecard.py          # Post-event: scores predictions vs results → recap tweet + ledger
├── data/                         # Runtime data (gitignored except fighters_db.json)
├── output/visuals/               # Generated images + videos
├── assets/
│   ├── fonts/                    # Bebas Neue + Roboto (must be present — see assets/fonts/README.md)
│   ├── images_cache/             # Cached fighter portrait PNGs
│   └── backgrounds/              # Imagen-generated background cache
├── tools/
│   ├── healthcheck.py            # Post-pipeline coverage check (odds/AI/visuals/credentials)
│   ├── check_models.py           # Lists available Gemini models via live API call
│   ├── list_models_raw.py        # Raw model list dump
│   ├── test_imports.py           # Verifies all modules import cleanly
│   ├── verify_odds.py            # Quick odds scraper sanity check
│   ├── verify_odds_scraper.py    # Full Betist + BFO scraper validation
│   ├── verify_twitter_api.py     # Twitter credential check
│   ├── audit_betting_system.py   # Betting pipeline audit
│   ├── prefetch_fighter_images.py # Multi-source portrait prefetch
│   ├── setup_twitter_cookies.py  # twikit cookie bootstrap
│   ├── show_tweets.py / check_data.py # Inspection helpers
│   ├── test_complete_extraction.py # End-to-end odds extraction test
│   └── test_imagen.py            # Imagen API connectivity test
└── tests/
    ├── test_units.py             # PYTEST unit tests (naming, streaks, parlay logic) — runs in CI
    ├── simulate_week.py          # Generates mock week of IDLE content
    ├── test_idle_modes.py        # Validates day→mode mapping
    ├── test_full_cycle.py        # Integration test (no API calls)
    ├── test_creative_modes.py    # Validates all 5 creative content modes
    ├── test_live_odds_connection.py # Validates live odds scraper connectivity
    ├── test_notifier.py          # Discord notifier unit test
    └── debug_bfo_detail_page.py  # BestFightOdds detail page scraper debug
```

---

## Pipeline Safety (stale-input guards)

Every producer stamps its stage in `data/pipeline_meta.json` via
`core.pipeline_meta.stamp_stage()`; consumers call `require_fresh_stage()` /
`check_stage_fresh()` and abort (exit 1) when the input is missing, older than
`PIPELINE_STAGE_MAX_AGE_HOURS`, or stamped for a different event. The Social
Director additionally refuses to post LIVE content when `3_results` is stale
and skips `spotlight_ready.json` files older than 20h. Event Radar writes
`status: ERROR` (and exits 1) instead of leaving a stale card behind.

All generated visuals use ONE sanitizer: `core.naming.safe_filename()`.
Never build a `Card_/Radar_/Versus_/Reel_/Pick_` filename by hand.

---

## Betting-Odds Honesty (never invent a price)

- `core/odds_resolve.py` treats the scraped **board as authoritative**. The
  model's quoted price is accepted only when it matches a real board price
  within ±5% (`AI_ODDS_BOARD_TOLERANCE`); otherwise the pick resolves against
  the board or falls back to the winner's ML. No board price → `odds_available:
  False` and the betting tweet is left **blank** (never published).
- Every published price is stamped with `odds_source` (Betist / BestFightOdds /
  …). `tools/healthcheck.py::check_content_safety()` flags any priced pick with
  no source as a possible invented-odds leak.
- Internal metric names (`ranking_proxy`, `injury_news_flag`, …) are scrubbed
  from all tweet text by `prediction_validate.scrub_internal_terms()`.

## Published-Pick Honesty (Live Wire + Scorecard)

- The Social Director writes `data/published_picks.json` when a betting tweet
  actually goes out (bet, bet_type, odds, predicted winner/method, whether the
  Pick card — and thus the confidence number — was published).
- Fight-night reactions (`_13_live_wire`) and the recap (`_14_scorecard`) may
  only claim "we called it" for picks recorded there. `evaluate_published_pick`
  grades the PUBLISHED bet against the real result into FULL_WIN / WINNER_ONLY /
  LOSS / NO_PICK, and the reaction template is chosen in code — no more "CASH
  IT" on a bet that lost, no confidence numbers that were never published.
- Live Wire runs a 12h window (18:00→06:00 UTC) and exits early once every
  fight has a result, so the main event is always covered. The scorecard only
  posts at ≥90% card coverage (`SCORECARD_MIN_COVERAGE`) and states partial
  coverage explicitly ("11 of 13 fights scored").

## Visual outputs (`output/visuals/`)

`Versus_*` (stat tale-of-tape) · `Pick_*` (AI PICK card: winner/method/
confidence bar/verified-odds/edge) · `Card_*` (single-fighter) · `Radar_*` ·
`Ticket_{Safe,Violence,Value}.png` · `Reel_*` (video). Betting tweets carry
**two** images: the Pick card then the Versus card.

## Runtime data files

`published_picks.json` (claim ledger) · `content_hashes.json` (7-day repeat
lock) · `prediction_ledger.json` (all-time accuracy, git-persisted) ·
`pipeline_meta.json` (stage stamps).

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
# AI Models (in priority order — confirmed working 2026-05-14)
GEMINI_MODELS = [
    "models/gemini-3.1-pro-preview",   # PRIMARY (God Mode)
    "models/gemini-2.5-pro",           # SECONDARY
    "models/gemini-2.5-flash",         # FALLBACK
]

# Image Generation (override with env FIGHTIQ_IMAGEN_MODEL)
IMAGEN_MODEL = "imagen-3.0-generate-002"  # + fallbacks in IMAGEN_MODEL_FALLBACKS

# Parlay thresholds
PARLAY_SAFE_CONFIDENCE = 7    # Min AI confidence score (0-10), fallback 6
PARLAY_VIOLENCE_SCORE = 75    # Min violence score (0-100), fallback 65

# Odds scraper (override with env BETIST_REDIRECT_URL if the shortlink dies)
BETIST_REDIRECT_URL = "https://cutt.ly/zrIT6E9d"

# Pipeline safety
PIPELINE_STAGE_MAX_AGE_HOURS = 36   # Stale-input guard threshold
POSTED_HISTORY_MAX_ENTRIES = 400    # posted_history.json cap

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
