#!/bin/zsh
# run_watcher.sh — Reference script for running Regulation Watcher
#
# NOTE: The actual LaunchAgent uses ~/scripts/mata-garuda-watcher.sh
# (TCC-safe bridge) — NOT this file. This is here for manual runs.
#
# Manual usage:
#   cd ~/Desktop/mata-garuda && source .venv/bin/activate
#   ./scripts/run_watcher.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/Users/nuzantara/logs/mata-garuda-watcher.log"

echo "" >> "$LOG"
echo "=== Regulation Watcher — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

cd "$REPO_DIR"
python -m mata_garuda.cli run "Regulation Watcher" \
    "check latest regulations" \
    --lamarckian \
    >> "$LOG" 2>&1

EXIT_CODE=$?
echo "[$(date '+%H:%M:%S')] Watcher exit=$EXIT_CODE" >> "$LOG"
exit $EXIT_CODE
