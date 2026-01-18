#!/bin/bash
#
# Setup Scribe Cron Job
# Installs or updates the cron job for automatic documentation generation
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/scribe_cron.sh"
CRON_SCHEDULE="0 2 * * *"  # Daily at 2 AM

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "scribe_cron.sh"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "scribe_cron.sh" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_SCRIPT") | crontab -

echo "✅ Scribe cron job installed!"
echo "   Schedule: Daily at 2:00 AM"
echo "   Script: $CRON_SCRIPT"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove: crontab -e (then delete the line)"
