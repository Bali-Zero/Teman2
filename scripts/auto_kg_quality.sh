#!/bin/bash

# KG Advanced Quality Enhancement — Cron Job
# Schedule: Every 48h (Air cron)
# Purpose: Normalize entity names, detect hierarchies, infer domain relations
#
# Pattern: same as auto_kb_ingest.sh
# Script: apps/backend-rag/scripts/kg_advanced_enhance.py

PROJECT_DIR="/Users/antonellosiano/Projects/nuzantara"
PYTHON_EXEC="/Users/antonellosiano/.pyenv/shims/python3"
BACKEND_DIR="$PROJECT_DIR/apps/backend-rag"
LOG_FILE="$PROJECT_DIR/logs/kg_quality.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

echo "[$DATE] Starting KG Quality Enhancement..." >> "$LOG_FILE"

# Check DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    # Try loading from .env
    if [ -f "$BACKEND_DIR/.env" ]; then
        export $(grep -v '^#' "$BACKEND_DIR/.env" | grep DATABASE_URL | xargs)
    fi
fi

if [ -z "$DATABASE_URL" ]; then
    echo "[$DATE] ERROR: DATABASE_URL not set. Skipping." >> "$LOG_FILE"
    exit 1
fi

# Run enhancement (--apply = not dry run)
cd "$BACKEND_DIR" || exit 1
export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"

echo "[$DATE] Running advanced KG enhancement (all collections)..." >> "$LOG_FILE"
"$PYTHON_EXEC" -m scripts.kg_advanced_enhance --apply >> "$LOG_FILE" 2>&1
STATUS=$?

if [ $STATUS -eq 0 ]; then
    echo "[$DATE] KG Quality Enhancement complete." >> "$LOG_FILE"
else
    echo "[$DATE] KG Quality Enhancement FAILED (exit $STATUS)." >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
