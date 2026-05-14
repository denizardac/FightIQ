#!/bin/bash

# ==========================================
# 🚀 FIGHTIQ DEPLOYMENT SCRIPT
# ==========================================

echo "=============================================="
echo "🚀 FIGHTIQ DEPLOYMENT & RESTART"
echo "=============================================="

# Configuration
PROJECT_DIR="/root/FightIQ"  # UPDATE THIS PATH
LOG_FILE="logs/deploy.log"
VENV_PATH="venv/bin/activate"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    echo -e "${RED}❌ ERROR: $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

# Change to project directory
cd "$PROJECT_DIR" || error_exit "Could not change to project directory: $PROJECT_DIR"
log "📁 Changed to project directory: $PROJECT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs
log "📂 Logs directory ready"

# Check for uncommitted changes (optional warning)
if [[ -n $(git status -s) ]]; then
    echo -e "${YELLOW}⚠️  Warning: Uncommitted local changes detected${NC}"
    echo -e "${YELLOW}   Proceeding with deployment...${NC}"
fi

# Fetch latest changes
log "🔄 Fetching latest changes from remote..."
git fetch origin || error_exit "Git fetch failed"

# Check if update is available
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" = "$REMOTE" ]; then
    log "✅ Already up to date (no changes to pull)"
else
    log "📥 Update available, pulling changes..."
    
    # Stash local changes (if any)
    if [[ -n $(git status -s) ]]; then
        log "📦 Stashing local changes..."
        git stash
    fi
    
    # Pull changes
    git pull origin main || error_exit "Git pull failed"
    log "✅ Successfully pulled latest changes"
    
    # Pop stash (if we stashed)
    if [[ -n $(git stash list) ]]; then
        log "📤 Restoring stashed changes..."
        git stash pop || echo -e "${YELLOW}⚠️  Stash pop had conflicts, resolve manually${NC}"
    fi
fi

# Activate virtual environment (if exists)
if [ -f "$VENV_PATH" ]; then
    log "🐍 Activating virtual environment..."
    source "$VENV_PATH" || error_exit "Could not activate virtual environment"
else
    log "⚠️  No virtual environment found, using system Python"
fi

# Install/update dependencies
log "📦 Checking dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet || error_exit "Dependency installation failed"
    log "✅ Dependencies up to date"
else
    log "⚠️  No requirements.txt found, skipping dependency check"
fi

# Verify critical files exist
log "🔍 Verifying critical files..."
CRITICAL_FILES=(
    ".env"
    "core/config.py"
    "core/main.py"
    "run.py"
    "data/fighters_db.json"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}⚠️  Warning: $file not found${NC}"
    fi
done

# Check environment variables
log "🔐 Checking environment configuration..."
if [ -f ".env" ]; then
    if grep -q "GEMINI_API_KEY=" .env && grep -q "X_API_KEY=" .env; then
        log "✅ Environment variables configured"
    else
        echo -e "${YELLOW}⚠️  Warning: API keys might be missing in .env${NC}"
    fi
else
    echo -e "${RED}❌ ERROR: .env file not found${NC}"
    error_exit "Missing .env file - deployment cannot proceed"
fi

# Run database check (optional)
log "🗄️  Checking fighter database..."
if [ -f "data/fighters_db.json" ]; then
    DB_SIZE=$(stat -f%z "data/fighters_db.json" 2>/dev/null || stat -c%s "data/fighters_db.json" 2>/dev/null)
    if [ "$DB_SIZE" -lt 1000 ]; then
        echo -e "${YELLOW}⚠️  Warning: Fighter database seems small (${DB_SIZE} bytes)${NC}"
        echo -e "${YELLOW}   Consider running: python modules/_00_indexer.py${NC}"
    else
        log "✅ Fighter database OK (${DB_SIZE} bytes)"
    fi
else
    echo -e "${YELLOW}⚠️  Warning: data/fighters_db.json not found${NC}"
    echo -e "${YELLOW}   Run: python modules/_00_indexer.py${NC}"
fi

# Test import (dry run)
log "🧪 Testing Python imports..."
python3 -c "from core.main import main" 2>/dev/null
if [ $? -eq 0 ]; then
    log "✅ Python imports successful"
else
    echo -e "${YELLOW}⚠️  Warning: Some Python imports failed${NC}"
fi

# ==========================================
# CRON JOB SETUP (optional — run with --setup-cron)
# ==========================================
PYTHON_BIN=$(which python3)
if [ -f "$VENV_PATH" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
fi

if [[ "$1" == "--setup-cron" ]]; then
    log "⏰ Setting up cron jobs..."

    # Remove any existing FightIQ cron entries
    crontab -l 2>/dev/null | grep -v "FightIQ" | crontab -

    # Add new entries
    (crontab -l 2>/dev/null; cat <<CRON
# FightIQ — Daily pipeline at 09:00 UTC (every day)
0 9 * * * $PYTHON_BIN $PROJECT_DIR/run.py >> $PROJECT_DIR/logs/cron.log 2>&1

# FightIQ — Live Wire fight night: Saturday 18:00 UTC (prelims start ~18:00, main card ~22:00)
0 18 * * 6 $PYTHON_BIN $PROJECT_DIR/modules/_13_live_wire.py --auto >> $PROJECT_DIR/logs/livewire.log 2>&1

# FightIQ — Live Wire fight night: Sunday 18:00 UTC
0 18 * * 0 $PYTHON_BIN $PROJECT_DIR/modules/_13_live_wire.py --auto >> $PROJECT_DIR/logs/livewire.log 2>&1
CRON
    ) | crontab -

    log "✅ Cron jobs installed. Current crontab:"
    crontab -l | grep FightIQ
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE${NC}"
echo "=============================================="
log "✅ Deployment completed successfully"

# Summary
echo ""
echo "📊 DEPLOYMENT SUMMARY:"
echo "  - Git: Up to date"
echo "  - Dependencies: Installed"
echo "  - Config: Verified"
echo "  - Logs: $LOG_FILE"
echo ""
echo "🎯 NEXT STEPS:"
echo "  1. Run the bot manually once to verify:"
echo "     python3 run.py"
echo ""
echo "  2. Set up cron (run once):"
echo "     bash core/deploy.sh --setup-cron"
echo ""
echo "  3. Monitor logs:"
echo "     tail -f logs/fightiq.log"
echo ""
echo "🔥 FIGHT NIGHT (Live Wire):"
echo "  Auto-scheduled via cron: Sat & Sun at 20:00 UTC"
echo "  Manual override: python3 modules/_13_live_wire.py --auto"
echo ""
echo "=============================================="
