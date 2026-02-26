#!/bin/bash
#
# Setup Ollama Cron Jobs
# Configures Ollama to start at 1am and stop at 6am
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/ollama_cron_window.sh"

echo "🔧 Setting up Ollama cron jobs (1am-6am window)..."

# Backup existing crontab
BACKUP_FILE="$PROJECT_ROOT/crontab.backup.ollama.$(date +%Y%m%d-%H%M%S)"
crontab -l > "$BACKUP_FILE" 2>/dev/null || echo "# Empty crontab" > "$BACKUP_FILE"
echo "✅ Backed up crontab to: $BACKUP_FILE"

# Remove old Ollama cron jobs
TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null | grep -v "ollama_cron_window.sh" | grep -v "^#" | grep -v "^$" > "$TEMP_CRON" || true

# Add Ollama cron jobs
(cat "$TEMP_CRON"; cat <<EOF

# ==========================================
# OLLAMA FOR AGENT TESTS (3:30 AM)
# ==========================================

# Start Ollama at 3:25 AM (5 min before agent tests)
25 3 * * * $CRON_SCRIPT start >> $PROJECT_ROOT/logs/ollama_cron.log 2>&1

# Stop Ollama at 3:35 AM (5 min after agent tests start - they should finish quickly)
35 3 * * * $CRON_SCRIPT stop >> $PROJECT_ROOT/logs/ollama_cron.log 2>&1
EOF
) | crontab -

rm "$TEMP_CRON"

echo ""
echo "✅ Ollama cron jobs configured!"
echo ""
echo "📋 Schedule:"
echo "  1:00 AM - Start Ollama (before tests)"
echo "  6:05 AM - Stop Ollama (after tests)"
echo ""
echo "📝 Logs: $PROJECT_ROOT/logs/ollama_cron.log"
echo "🔍 Check status: $CRON_SCRIPT status"
echo ""
echo "📋 View cron: crontab -l"
