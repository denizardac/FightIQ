"""
FightIQ Configuration
Centralized configuration for thresholds, magic numbers, and settings
"""

import os

# ==========================================
# FIGHTER SELECTION THRESHOLDS
# ==========================================

# Violence Mode
VIOLENCE_SLPM_THRESHOLD = 4.0      # Primary threshold for violence candidates
VIOLENCE_SLPM_RELAXED = 3.0        # Relaxed threshold for retry
VIOLENCE_MIN_SLPM = 2.5            # Absolute minimum

# History Mode
HISTORY_WINS_THRESHOLD = 20        # Primary threshold for veterans
HISTORY_WINS_RELAXED = 15          # Relaxed threshold for retry
HISTORY_MIN_WINS = 10              # Absolute minimum

# Standard Mode
STANDARD_MIN_WINS = 10             # Minimum wins for standard content
STANDARD_MIN_WINS_RELAXED = 5      # Relaxed minimum wins for fallback

# Anomaly Mode
ANOMALY_ODDS_THRESHOLD = 2.20      # Minimum odds for underdog value
ANOMALY_STAT_DIFF_THRESHOLD = 15   # Stat difference % for statistical anomalies

# ==========================================
# MODE SELECTION & RETRY LOGIC
# ==========================================

MAX_RETRIES_PER_MODE = 2           # How many times to retry with relaxed criteria
MAX_FIGHTERS_TO_SCAN = 100         # Maximum fighters to check per mode
MAX_CANDIDATE_PAIRS = 10           # For ORACLE/ANOMALY modes

# ==========================================
# BETIST (LIVE ODDS) SETTINGS
# ==========================================

# Redirect that always points to Betist's current live domain (auto-discovery).
# dub.sh/betist 302s to the current betistXXXX.com; override if it ever dies.
BETIST_REDIRECT_URL = os.environ.get("BETIST_REDIRECT_URL", "https://dub.sh/betist")
BETIST_KNOWN_LEAGUE_IDS = ["41875249", "41875250", "30582", "41875251"]
BETIST_REQUEST_TIMEOUT = 15
BETIST_RETRY_DELAY = 2             # Seconds between retries

# ==========================================
# NAME MATCHING
# ==========================================

FUZZY_MATCH_CUTOFF = 0.8           # Primary High Confidence
FUZZY_MATCH_CUTOFF_MEDIUM = 0.75   # Betist/Smart Match
FUZZY_MATCH_CUTOFF_RELAXED = 0.7   # General Relaxed
FUZZY_MATCH_CUTOFF_LOW = 0.6       # BFO/Fallback Low Confidence

# ==========================================
# FIGHT WEEK CONFIG
# ==========================================

# Fight Week - Parlay Thresholds
PARLAY_SAFE_CONFIDENCE = 7          # Min confidence for safe slip (primary)
PARLAY_SAFE_CONFIDENCE_FALLBACK = 6 # Used when building fallback safe slip
PARLAY_VIOLENCE_SCORE = 75          # Min violence score for violence slip (primary)
PARLAY_VIOLENCE_SCORE_FALLBACK = 65 # Fallback violence slip
PARLAY_MAX_LEGS = 3                 # Max legs per slip (all types)

# Value / Edge slip — model-aligned, winnable 3-leg parlay
VALUE_SLIP_MIN_CONFIDENCE = 6
VALUE_SLIP_MIN_LEG_ODDS = 1.45
VALUE_SLIP_MAX_LEG_ODDS = 8.0   # Method / rounds props allowed on edge slip
VALUE_SLIP_MAX_COMBINED_ODDS = 25.0
SAFE_SLIP_MAX_ODDS = 2.25

# Fight Week - AI Rate Limiting
AI_REQUEST_DELAY_SECONDS = 3    # Delay between AI requests
AI_MAX_RETRIES = 2               # Max retries for failed AI calls

# ==========================================
# ORACLE MODE MATCHUP QUALITY
# ==========================================

ORACLE_MAX_WINS_DIFFERENCE = 5     # Max difference in wins for comparable fighters
ORACLE_PREFER_TRENDING = True       # Prioritize trending fighters

# ==========================================
# LIVE WIRE (COMMENTARY) CONFIG
# ==========================================

LIVE_WIRE_POLL_INTERVAL = 60       # Seconds between checks in continuous mode
# 18:00 UTC start + 12h = 06:00 UTC — covers the MAIN EVENT (the old 8h window
# closed at 02:00, before the main card finished, so headliners were never
# reacted to or scored). Loop also exits early once every fight has a result.
LIVE_WIRE_MAX_RUNTIME_HOURS = 12
# Scorecard recap only posts when at least this share of the card is scored
SCORECARD_MIN_COVERAGE = 0.9
SPOTLIGHT_HISTORY_DAYS = 90        # Days to look back for content history

# ==========================================
# TWITTER / X POSTING
# ==========================================

# Cookie/twikit pacing (reduces Twitter error 226 on VPS)
TWITTER_PRE_POST_DELAY_SECONDS = int(os.environ.get("TWITTER_PRE_POST_DELAY_SECONDS", "25"))
TWITTER_THREAD_DELAY_SECONDS = int(os.environ.get("TWITTER_THREAD_DELAY_SECONDS", "90"))
TWITTER_POST_DELAY_SECONDS = int(os.environ.get("TWITTER_POST_DELAY_SECONDS", "60"))
TWITTER_LIVE_CONTENT_DELAY_SECONDS = int(os.environ.get("TWITTER_LIVE_CONTENT_DELAY_SECONDS", "180"))
TWITTER_DELAY_JITTER_SECONDS = int(os.environ.get("TWITTER_DELAY_JITTER_SECONDS", "20"))
# twikit error 226 retries
TWITTER_226_MAX_RETRIES = int(os.environ.get("TWITTER_226_MAX_RETRIES", "4"))
TWITTER_226_BASE_DELAY = int(os.environ.get("TWITTER_226_BASE_DELAY", "120"))

# ==========================================
# CONTENT GENERATION (GOD MODE - Phase 3)
# ==========================================

# PRIMARY AI MODELS - Maximum Intelligence & Reasoning
# Primary: User-specified. Fallbacks: confirmed working via live API test (2026-03-26)
GEMINI_MODELS = [
    "models/gemini-3.1-pro-preview",    # PRIMARY (God Mode) — confirmed 2026-05-14
    "models/gemini-2.5-pro",            # SECONDARY — confirmed 2026-05-14
    "models/gemini-2.5-flash",          # FALLBACK — confirmed 2026-05-14
]

# Image generation (Gemini API). Override with env FIGHTIQ_IMAGEN_MODEL if needed.
# Old preview id often 404s on v1beta; fallbacks tried in core.imagen_utils.
IMAGEN_MODEL = os.environ.get("FIGHTIQ_IMAGEN_MODEL", "imagen-3.0-generate-002")
IMAGEN_MODEL_FALLBACKS = [
    "imagen-3.0-fast-generate-001",
    "imagen-3.0-generate-001",
    "models/imagen-3.0-generate-002",
    "models/imagen-4.0-generate-preview-06-06",
]

# AI Configuration
AI_TEMPERATURE = 0.4  # Spotlight / creative content
AI_TEMPERATURE_PREDICTION = 0.25  # Fight Brain — tighter, sharper picks
AI_TOP_P = 0.95       # Nucleus sampling for diverse outputs
AI_TOP_K = 40         # Limit vocabulary to top 40 tokens


# ==========================================
# BRAND IDENTITY
# ==========================================

BRAND_COLORS = {
    "primary": "#00FF41",      # FightIQ Green
    "secondary": "#FFD700",    # Gold
    "accent": "#FF0055",       # Red
    "bg_dark": "#0a0a0a",      # Deep Black
    "bg_card": "#1a1a1a",      # Card Background
    "text_light": "#EEEEEE",   # Light Text
    "text_white": "#FFFFFF",   # Pure White
    "text_dark": "#AAAAAA"     # Dark Gray
}

# Font Paths
FONT_PATHS = {
    "headline": "assets/fonts/BebasNeue-Regular.ttf",      # Headlines/Titles
    "body_bold": "assets/fonts/Roboto-Bold.ttf",           # Body Bold
    "body_regular": "assets/fonts/Roboto-Regular.ttf"      # Body Regular
}

# ==========================================
# PIPELINE SAFETY
# ==========================================

# Stale-input guard: a stage output older than this (or stamped for another
# event) aborts the pipeline instead of publishing content for the wrong card.
PIPELINE_STAGE_MAX_AGE_HOURS = 36

# posted_history.json cap — oldest entries pruned beyond this
POSTED_HISTORY_MAX_ENTRIES = 400

# ==========================================
# LOGGING
# ==========================================

LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "fightiq.log"
LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT = 5
