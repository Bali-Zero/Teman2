#!/bin/bash
# Nightly Git Sync Air ← Pro
# Called by com.nuzantara.nightly-sync LaunchAgent at 02:30 WITA
set -euo pipefail

PROJECT_DIR="/Users/antonellosiano/Projects/nuzantara"
LOG="/tmp/nuzantara-nightly-sync.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$DATE] Nightly git sync Air←Pro starting..." >> "$LOG"
cd "$PROJECT_DIR"

# Pull from Pro (ff-only to stay safe)
if git pull pro main --ff-only >> "$LOG" 2>&1; then
  echo "[$DATE] ✅ Git sync OK ($(git log --oneline -1))" >> "$LOG"
else
  echo "[$DATE] ⚠️  Git sync skipped (not fast-forward or no remote)" >> "$LOG"
fi
echo "[$DATE] Done." >> "$LOG"
