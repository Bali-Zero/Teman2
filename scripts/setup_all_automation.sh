#!/bin/bash
#
# Setup All Automation Cron Jobs
# Configures all recommended cron jobs for Nuzantara platform
#
# This script:
# 1. Backs up existing crontab
# 2. Removes duplicate/old cron jobs
# 3. Sets up all automation cron jobs with optimal schedule
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔧 Setting up Nuzantara automation cron jobs..."
echo ""

# Backup existing crontab
BACKUP_FILE="$PROJECT_ROOT/crontab.backup.$(date +%Y%m%d-%H%M%S)"
crontab -l > "$BACKUP_FILE" 2>/dev/null || echo "# Empty crontab" > "$BACKUP_FILE"
echo "✅ Backed up existing crontab to: $BACKUP_FILE"

# Remove old/duplicate cron jobs
echo "🧹 Cleaning up old cron jobs..."
TEMP_CRON=$(mktemp)
# Remove old auto_scribe.sh and keep only unique lines (remove duplicates)
crontab -l 2>/dev/null | \
  grep -v "auto_scribe.sh" | \
  grep -v "^#" | \
  grep -v "^$" | \
  awk '!seen[$0]++' > "$TEMP_CRON" || true

# Add all automation cron jobs
echo "📅 Adding automation cron jobs..."
(cat "$TEMP_CRON"; cat <<EOF

# ==========================================
# NUZANTARA AUTOMATION CRON JOBS
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# ==========================================

# Documentation (Scribe) - Daily at 2:00 AM
0 2 * * * $PROJECT_ROOT/scripts/scribe_cron.sh >> $PROJECT_ROOT/logs/scribe_cron.log 2>&1

# Quality Control (Sentinel) - Daily at 3:00 AM
0 3 * * * $PROJECT_ROOT/scripts/auto_sentinel.sh >> $PROJECT_ROOT/logs/sentinel_nightly.log 2>&1

# Database Backup - Daily at 1:00 AM (before Scribe)
0 1 * * * $PROJECT_ROOT/scripts/backup-db.sh >> $PROJECT_ROOT/logs/backup.log 2>&1

# Daily Monitoring - Daily at 8:00 AM (after all night processes)
0 8 * * * $PROJECT_ROOT/scripts/daily-monitoring.sh >> $PROJECT_ROOT/logs/daily_monitoring.log 2>&1

# Ollama Start - Daily at 2:00 AM (for Test Force - needs 2 hours window)
0 2 * * * $PROJECT_ROOT/scripts/ollama_cron_window.sh start >> $PROJECT_ROOT/logs/ollama_cron.log 2>&1

# Test Force Orchestrator - Daily at 2:15 AM (intelligent test generation/maintenance)
# Uses Qwen to: analyze coverage, generate tests, modify tests, delete obsolete tests
# Estimated duration: 45-90 minutes
15 2 * * * $PROJECT_ROOT/scripts/auto_test_force.sh >> $PROJECT_ROOT/logs/test_force.log 2>&1

# Agent Tests - Daily at 3:30 AM (after Test Force, before data collection)
# Ollama should already be running from 2:00am cron
30 3 * * * $PROJECT_ROOT/scripts/auto_agent_test.sh >> $PROJECT_ROOT/logs/agent_test.log 2>&1

# Ollama Stop - Daily at 4:00 AM (after Test Force and Agent Tests complete)
0 4 * * * $PROJECT_ROOT/scripts/ollama_cron_window.sh stop >> $PROJECT_ROOT/logs/ollama_cron.log 2>&1

# Intel Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * $PROJECT_ROOT/scripts/auto_intel_scraper.sh >> $PROJECT_ROOT/logs/intel_scraper.log 2>&1
0 16 * * * $PROJECT_ROOT/scripts/auto_intel_scraper.sh >> $PROJECT_ROOT/logs/intel_scraper.log 2>&1

# KB Ingest - Daily at 5:00 AM
0 5 * * * $PROJECT_ROOT/scripts/auto_kb_ingest.sh >> $PROJECT_ROOT/logs/kb_ingest.log 2>&1

# News Enricher - Every 6 hours (0:00, 6:00, 12:00, 18:00)
0 0,6,12,18 * * * $PROJECT_ROOT/apps/bali-intel-scraper/scripts/run_news_enricher.sh >> $PROJECT_ROOT/logs/news_enricher.log 2>&1

# Judgement Day - Sunday at 4:00 PM
0 16 * * 0 $PROJECT_ROOT/scripts/auto_judgement_day.sh >> $PROJECT_ROOT/logs/judgement_day.log 2>&1

# Unified Scraper - Daily at 4:00 AM and 4:00 PM
0 4 * * * cd $PROJECT_ROOT/apps/bali-intel-scraper/scripts && /usr/bin/python3 unified_scraper.py >> $PROJECT_ROOT/logs/scrapers/unified_scraper.log 2>&1
0 16 * * * cd $PROJECT_ROOT/apps/bali-intel-scraper/scripts && /usr/bin/python3 unified_scraper.py >> $PROJECT_ROOT/logs/scrapers/unified_scraper.log 2>&1

# Visa Agent - Daily at 4:00 AM and 4:00 PM
0 4 * * * cd $PROJECT_ROOT/apps/kb && /usr/bin/python3 intelligent_visa_agent.py >> $PROJECT_ROOT/logs/scrapers/visa_agent.log 2>&1
0 16 * * * cd $PROJECT_ROOT/apps/kb && /usr/bin/python3 intelligent_visa_agent.py >> $PROJECT_ROOT/logs/scrapers/visa_agent.log 2>&1
EOF
) | crontab -

rm "$TEMP_CRON"

echo ""
echo "✅ All automation cron jobs configured!"
echo ""
echo "📋 View cron jobs: crontab -l"
echo "📁 Backup saved to: $BACKUP_FILE"
echo ""
echo "📊 Schedule Overview:"
echo "  1:00 AM  - DB Backup"
echo "  2:00 AM  - Ollama Start (for Test Force - 2 hour window)"
echo "  2:00 AM  - Scribe (Documentation)"
echo "  2:15 AM  - Test Force Orchestrator (Qwen: generate/modify/delete tests)"
echo "  3:00 AM  - Sentinel (Quality Control)"
echo "  3:30 AM  - Agent Tests (Agentic RAG with Ollama Qwen)"
echo "  4:00 AM  - Ollama Stop (after Test Force and Agent Tests)"
echo "  4:00 AM  - Intel Scraper + Visa Agent + Unified Scraper"
echo "  5:00 AM  - KB Ingest"
echo "  8:00 AM  - Daily Monitoring"
echo "  4:00 PM  - Intel Scraper + Visa Agent + Unified Scraper"
echo "  Sunday 4:00 PM - Judgement Day"
echo ""
echo "📝 Logs location: $PROJECT_ROOT/logs/"
echo ""
echo "📊 View test results:"
echo "   ./scripts/view_test_results.sh"
echo ""
echo "📈 Generate HTML report:"
echo "   ./scripts/generate_test_report.sh"
