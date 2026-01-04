#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Desktop/nuzantara"
PYTHON_EXEC="/Users/antonellosiano/.pyenv/shims/python3"
SCRAPER_DIR="$PROJECT_DIR/apps/bali-intel-scraper"
LOG_FILE="$PROJECT_DIR/logs/intel_scraper.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Intel Scraper (Mode: Full)..." >> "$LOG_FILE"
cd "$SCRAPER_DIR"

# Run the pipeline in full mode
# This triggers: Scrape -> Score -> Validate -> Enrich -> Image -> SEO -> Telegram Approval
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:$PYTHONPATH"
"$PYTHON_EXEC" scripts/run_intel_feed.py --mode full >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Scraper completed. Approval requests sent to Telegram." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Scraper FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
