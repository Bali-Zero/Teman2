#!/usr/bin/env bash
# merge_train_run.sh — LaunchAgent wrapper for the merge-train coordinator.
# Spec: research/operations/specs/MERGE-TRAIN-coordinator-spec.md §10.7.
# launchd provides a bare env: absolute PATH, explicit cwd, logged output.
set -uo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO_ROOT="${MERGE_TRAIN_REPO_ROOT:-$HOME/Desktop/nuzantara}"
LOG_DIR="$HOME/logs"
mkdir -p "$LOG_DIR"

cd "$REPO_ROOT" || { echo "[merge-train] repo root missing: $REPO_ROOT" >> "$LOG_DIR/merge-train.log"; exit 1; }

{
  echo "--- tick $(date -u +%FT%TZ) ---"
  /usr/bin/env python3 scripts/merge_train.py
  echo "exit=$?"
} >> "$LOG_DIR/merge-train.log" 2>&1
