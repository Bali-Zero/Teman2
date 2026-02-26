#!/bin/bash
#
# Scribe Auto-Documentation Cron Job
# Runs Scribe daily to regenerate documentation
#
# Usage:
#   Add to crontab: 0 2 * * * /path/to/scripts/scribe_cron.sh >> /tmp/scribe_cron.log 2>&1
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/logs/scribe_cron.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Change to project root
cd "$PROJECT_ROOT"

# Log start
echo "[$TIMESTAMP] Starting Scribe documentation generation..." >> "$LOG_FILE"

# Run Scribe (use python3 explicitly)
if python3 apps/core/scribe.py >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] ✅ Scribe completed successfully" >> "$LOG_FILE"
    
    # Optional: Commit changes to git (uncomment if desired)
    # git add docs/SYSTEM_MAP_4D.md docs/SYSTEM_OVERVIEW.md docs/LIVING_ARCHITECTURE.md
    # git commit -m "docs: Auto-update documentation $(date '+%Y-%m-%d')" || true
    
    exit 0
else
    echo "[$TIMESTAMP] ❌ Scribe failed - check logs" >> "$LOG_FILE"
    exit 1
fi
