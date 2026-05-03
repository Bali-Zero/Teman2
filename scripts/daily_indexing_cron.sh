#!/bin/bash
#
# Daily Google Search Console Indexing Sweep
# Runs: Phase 1 (Articles) + Phase 2 (KBLI)
# Schedule: Every day 00:30 WITA (17:30 UTC prev day)
# Logs to: logs/daily_indexing_sweep.log
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/daily_indexing_sweep.log"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/daily_indexing_sweep.py"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1" | tee -a "$LOG_FILE"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

log_info "═══════════════════════════════════════════════════════════════════"
log_info "Daily Indexing Sweep | $(date '+%Y-%m-%d %H:%M:%S')"
log_info "═══════════════════════════════════════════════════════════════════"

# Check Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    log_err "Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check venv
VENV_DIR="$PROJECT_ROOT/.venv"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    log_err "venv not found at $VENV_DIR"
    exit 1
fi

# Run sweep
cd "$PROJECT_ROOT"
"$VENV_DIR/bin/python" "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_ok "Sweep completed successfully"
    exit 0
else
    log_err "Sweep failed with exit code $EXIT_CODE"
    exit 1
fi
