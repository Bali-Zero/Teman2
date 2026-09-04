#!/usr/bin/env bash
# memory_recall_userprompt.sh — UserPromptSubmit receptor for MOS Layer 2b
# recall (mirrors memory_recall_sessionstart.sh's pattern). stdin is the
# hook JSON payload Claude Code sends on every prompt; passed through
# verbatim to the Python engine, which does its own prompt-shape quiet-gate
# and fails open (exit 0, silent) on any error. Kill switch:
# CLAUDE_RECALL_PROMPT_DISABLED=1.
set -u
exec python3 "${CLAUDE_PROJECT_DIR:-$PWD}/scripts/memory/mos_recall_userprompt.py" 2>/dev/null || exit 0
