#!/bin/bash
#
# Daily Indexing Sweep Cron Wrapper
# Ensures venv exists and activates it before running the sweep.
# Runs on Air (target: /Users/antonellosiano/Projects/nuzantara).
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/daily_indexing_sweep.log"

# Ensure log dir exists
mkdir -p "$LOG_DIR"

{
  echo "==============================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Daily Indexing Sweep started"
  echo "==============================================================================="

  # Check venv; create if missing
  if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[INFO] venv not found at $VENV_DIR, creating..."
    python3 -m venv "$VENV_DIR"

    # Install requirements
    echo "[INFO] Installing requirements..."
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
  fi

  # Activate and run
  source "$VENV_DIR/bin/activate"
  cd "$PROJECT_ROOT"

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
