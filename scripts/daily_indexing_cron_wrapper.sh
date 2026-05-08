#!/bin/bash
#
# Daily Indexing Sweep Cron Wrapper
# Submits unindexed articles + KBLI pages to Google Indexing API (daily quota-based).
# Phase 1 (articles): max 200/day | Phase 2 (KBLI): max 600/day
# Updates state JSON files and sends summary to Telegram.
#
# Runs on Pro: /Users/nuzantara/Desktop/nuzantara

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/daily_indexing_sweep.log"

# Ensure log dir exists
mkdir -p "$LOG_DIR"

{
  echo "==============================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Daily Indexing Sweep started (Pro)"
  echo "==============================================================================="

  # Activate venv (required for import chain). Bootstrap if missing so a
  # fresh Pro provision self-heals — matches pre-2026-05-07 behavior.
  if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[INFO] .venv not found at $VENV_DIR, creating..."
    python3 -m venv "$VENV_DIR"
    echo "[INFO] Installing requirements..."
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
  fi

  source "$VENV_DIR/bin/activate"
  cd "$PROJECT_ROOT"
  export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

  # Run sweep (both Phase 1: articles + Phase 2: KBLI)
  python scripts/daily_indexing_sweep.py
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    echo "[OK] Sweep completed successfully"
  else
    echo "[ERROR] Sweep failed with exit code $EXIT_CODE"
  fi

  echo "==============================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Completed (exit $EXIT_CODE)"
  echo "==============================================================================="

  exit $EXIT_CODE
} 2>&1 | tee -a "$LOG_FILE"
