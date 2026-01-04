#!/bin/bash
# Cron job script for RSS fetcher
# Add to crontab with: crontab -e
# Run every 6 hours: 0 */6 * * * /path/to/cron_fetcher.sh

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/../logs"
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log start
echo "======================================" >> "$LOG_FILE"
echo "RSS Fetcher started at $(date)" >> "$LOG_FILE"

# Run the fetcher
cd "$SCRIPT_DIR/.." && \
  python scripts/rss_fetcher.py \
    --max-age 5 \
    --limit 10 \
    --api-url https://balizero.com \
    --send >> "$LOG_FILE" 2>&1

# Log completion
echo "RSS Fetcher completed at $(date)" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"
