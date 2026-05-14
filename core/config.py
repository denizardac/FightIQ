"""
FightIQ Configuration
Centralized configuration for thresholds, magic numbers, and settings
"""

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

BETIST_REDIRECT_URL = "https://cutt.ly/zrIT6E9d"
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
PARLAY_SAFE_CONFIDENCE = 8      # Min confidence for safe slip
PARLAY_VIOLENCE_SCORE = 80      # Min violence score for violence slip

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
SPOTLIGHT_HISTORY_DAYS = 90        # Days to look back for content history

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

# Image Generation - Imagen 4
IMAGEN_MODEL = "models/imagen-4.0-generate-preview-06-06"

# AI Configuration
AI_TEMPERATURE = 0.4  # Increased for creative reasoning (was 0.2)
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
# LOGGING
# ==========================================

LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "fightiq.log"
LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT = 5
