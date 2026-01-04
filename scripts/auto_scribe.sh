#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Desktop/nuzantara"
PYTHON_EXEC="/Users/antonellosiano/.pyenv/shims/python3"
LOG_FILE="$PROJECT_DIR/logs/scribe_cron.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Scribe auto-update..." >> "$LOG_FILE"
cd "$PROJECT_DIR"
"$PYTHON_EXEC" apps/core/scribe.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] Success." >> "$LOG_FILE"
else
    echo "[$DATE] Failed with exit code $EXIT_CODE." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
