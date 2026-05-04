#!/usr/bin/env bash
# subhi-mirror-and-publish.sh — daily wrapper invoked by LaunchAgent.
# Runs filter, then publish sentinel. On any failure, logs + exits non-zero.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/logs/subhi-mirror-and-publish.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== START daily mirror+publish ==="

if ! bash "$SCRIPT_DIR/subhi-memory-mirror.sh" 2>&1 | tee -a "$LOG"; then
  log "FAIL: mirror script returned non-zero"
  exit 1
fi

if ! bash "$SCRIPT_DIR/subhi-mirror-publish.sh" 2>&1 | tee -a "$LOG"; then
  log "FAIL: publish script returned non-zero"
  exit 2
fi

log "=== END daily mirror+publish OK ==="
