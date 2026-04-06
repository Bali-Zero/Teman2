#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Projects/nuzantara"
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

# Load secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID)
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
TELEGRAM_CHAT_ID="${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}"

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Sentinel PASSED." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Sentinel FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 *Air Sentinel FAILED* (exit $EXIT_CODE)%0ACheck: ~/Projects/nuzantara/logs/sentinel_nightly.log" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
fi

echo "----------------------------------------" >> "$LOG_FILE"
