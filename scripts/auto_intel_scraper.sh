#!/bin/bash
# Intel Scraper Cron Wrapper - macOS Compatible
# Fixes: Environment variables, PATH, Python path

# Load shell environment
export HOME="/Users/antonellosiano"
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null
[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null

# Set PATH with pyenv
export PATH="$HOME/.pyenv/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Project directory (auto-detect from script location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRAPER_DIR="$PROJECT_DIR/apps/bali-intel-scraper"
LOG_FILE="$PROJECT_DIR/logs/intel_scraper.log"

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log start
DATE=$(date "+%Y-%m-%d %H:%M:%S")
echo "[$DATE] Starting Intel Scraper (Mode: Full)..." >> "$LOG_FILE"
echo "[$DATE] PATH: $PATH" >> "$LOG_FILE"
echo "[$DATE] Python: $(which python3 2>&1)" >> "$LOG_FILE"

# Change to scraper directory
cd "$SCRAPER_DIR" || {
    echo "[$DATE] ❌ Failed to cd to $SCRAPER_DIR" >> "$LOG_FILE"
    exit 1
}

# Load .env.local if exists
if [ -f "$SCRAPER_DIR/.env.local" ]; then
    export $(grep -v '^#' "$SCRAPER_DIR/.env.local" | xargs)
    echo "[$DATE] Loaded .env.local" >> "$LOG_FILE"
    # Verify GOOGLE_API_KEY loaded
    if [ -n "$GOOGLE_API_KEY" ]; then
        echo "[$DATE] ✅ GOOGLE_API_KEY loaded (Imagen 4 enabled)" >> "$LOG_FILE"
    else
        echo "[$DATE] ⚠️  GOOGLE_API_KEY not found in .env.local" >> "$LOG_FILE"
    fi
fi

# Load NUZANTARA_API_KEY from environment or .env.local
if [ -z "$NUZANTARA_API_KEY" ]; then
    # Try to load from project root .env if exists
    if [ -f "$PROJECT_DIR/.env" ]; then
        export $(grep -v '^#' "$PROJECT_DIR/.env" | grep NUZANTARA_API_KEY | xargs)
    fi
fi

# Set API URL
export BACKEND_API_URL="${BACKEND_API_URL:-https://nuzantara-rag.fly.dev}"
export NUZANTARA_API_URL="${NUZANTARA_API_URL:-$BACKEND_API_URL}"

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:$PYTHONPATH"

# Find Python executable
PYTHON_EXEC=$(which python3)
if [ -z "$PYTHON_EXEC" ]; then
    echo "[$DATE] ❌ Python3 not found in PATH" >> "$LOG_FILE"
    exit 1
fi

# Run the pipeline
echo "[$DATE] Executing: $PYTHON_EXEC scripts/run_intel_feed.py --mode full --api-url $NUZANTARA_API_URL" >> "$LOG_FILE"
if [ -n "$NUZANTARA_API_KEY" ]; then
    echo "[$DATE] Using API key from environment" >> "$LOG_FILE"
    "$PYTHON_EXEC" scripts/run_intel_feed.py --mode full --api-url "$NUZANTARA_API_URL" --api-key "$NUZANTARA_API_KEY" >> "$LOG_FILE" 2>&1
else
    echo "[$DATE] ⚠️  No API key found - requests may fail" >> "$LOG_FILE"
    "$PYTHON_EXEC" scripts/run_intel_feed.py --mode full --api-url "$NUZANTARA_API_URL" >> "$LOG_FILE" 2>&1
fi
EXIT_CODE=$?

# Log result
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Scraper completed successfully." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Scraper FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
exit $EXIT_CODE
