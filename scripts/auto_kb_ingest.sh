#!/bin/bash

# Configuration
# Path-aware: works on Pro (~/Desktop/nuzantara) and on legacy Air
# (~/Projects/nuzantara). Air was decommissioned 2026-05-05; this script
# was originally hardcoded for Air.
if [ -d "$HOME/Desktop/nuzantara" ]; then
    PROJECT_DIR="$HOME/Desktop/nuzantara"
elif [ -d "$HOME/Projects/nuzantara" ]; then
    PROJECT_DIR="$HOME/Projects/nuzantara"
else
    echo "ERROR: could not locate nuzantara repo under \$HOME" >&2
    exit 1
fi
if [ -x "$HOME/.pyenv/shims/python3" ]; then
    PYTHON_EXEC="$HOME/.pyenv/shims/python3"
else
    PYTHON_EXEC="$(command -v python3)"
fi
KB_DIR="$PROJECT_DIR/apps/kb"
LOG_FILE="$PROJECT_DIR/logs/kb_ingest.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Knowledge Base Ingestion..." >> "$LOG_FILE"
cd "$PROJECT_DIR" # Run from root for imports

run_if_exists() {
    local script="$1"
    shift
    if [ -f "$script" ]; then
        export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:${PYTHONPATH:-}"
        "$PYTHON_EXEC" "$script" "$@" >> "$LOG_FILE" 2>&1
        return $?
    else
        echo "[$DATE] ⚠️  SKIP: $script not found" >> "$LOG_FILE"
        return 0
    fi
}

# 1. Intelligent Visa Agent (Vision + Map + Notifications)
echo "[$DATE] Running Intelligent Visa Agent..." >> "$LOG_FILE"
run_if_exists "apps/kb/intelligent_visa_agent.py"

# 2. Peraturan Spider (Laws) - Standard Update
echo "[$DATE] Running Peraturan Spider..." >> "$LOG_FILE"
run_if_exists "apps/kb/peraturan_spider.py" --limit 10

# 3. Putusan Spider (Court) - Standard Update
echo "[$DATE] Running Putusan Spider..." >> "$LOG_FILE"
run_if_exists "apps/kb/putusan_spider.py"

echo "[$DATE] ✅ KB Ingestion Cycle Complete." >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
