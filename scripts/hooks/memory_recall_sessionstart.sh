#!/usr/bin/env bash
# memory_recall_sessionstart.sh — SessionStart receptor for MOS Layer 2 recall.
set -u
exec python3 "${CLAUDE_PROJECT_DIR:-$PWD}/scripts/memory/mos_recall_sessionstart.py" 2>/dev/null || exit 0
