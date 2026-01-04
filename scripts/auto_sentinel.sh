#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Desktop/nuzantara"
LOG_FILE="$PROJECT_DIR/logs/sentinel_nightly.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Nightly Sentinel Run..." >> "$LOG_FILE"
cd "$PROJECT_DIR"

# Run Sentinel using the wrapper script
./sentinel >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Sentinel PASSED." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Sentinel FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
