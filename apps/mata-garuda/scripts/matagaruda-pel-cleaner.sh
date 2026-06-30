#!/bin/zsh
# matagaruda-pel-cleaner.sh — weekly PEL recovery cron wrapper
#
# W12 hardening (2026-05-22). Calls apps/mata-garuda/scripts/pel_cleaner.py
# which:
#   - XCLAIMs pending messages from stale consumers (idle>24h) to youngest
#     alive consumer in the same group
#   - XGROUP DELCONSUMER on zero-pending consumers idle>30d
#
# Designed for weekly launchd cron (Sunday 04:00 WITA) so manual ops can react
# to surprises during the week. Idempotent: re-running on clean state = no-op.
#
# Exit codes:
#   0 — clean (no actions OR all actions succeeded)
#   1 — at least one XCLAIM/DELCONSUMER errored (see JSON output)
#   75 — another instance running (flock lesson W7)
set -e

# Self-locating: APP_ROOT is this script's grandparent dir
# (<repo>/apps/mata-garuda/scripts/<this>.sh → :h:h). (cicatrix #1: no HOME-fork.)
APP_ROOT="${0:A:h:h}"
REPO_ROOT="${APP_ROOT:h:h}"
SCRIPT="${APP_ROOT}/scripts/pel_cleaner.py"
VENV_PY="${APP_ROOT}/.venv/bin/python"
LOG_DIR="$HOME/logs"
mkdir -p "$LOG_DIR"
LOCK_FILE="/tmp/matagaruda-pel-cleaner.lock"

# Single-instance gate (W7 lesson — concurrent crons stack on Redis ops)
exec /opt/homebrew/bin/flock --nonblock --exclusive --conflict-exit-code 75 "$LOCK_FILE" \
  bash -c "
    cd '${APP_ROOT}'
    if [ ! -x '${VENV_PY}' ]; then
        echo \"\$(date -Iseconds) FATAL: venv python missing at ${VENV_PY}\" >&2
        exit 2
    fi
    if [ ! -f '${SCRIPT}' ]; then
        echo \"\$(date -Iseconds) FATAL: cleaner script missing at ${SCRIPT}\" >&2
        exit 2
    fi
    '${VENV_PY}' '${SCRIPT}'
  "
