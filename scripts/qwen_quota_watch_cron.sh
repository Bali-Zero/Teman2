#!/usr/bin/env bash
# qwen_quota_watch_cron.sh — cron payload for cron-runner.sh (Pro, daily).
#
# cron-runner executes payloads with /bin/bash, so the python watcher needs
# this thin wrapper. It lives IN THE REPO and the crontab line points here
# directly (never a ~/scripts copy — superscar #1 HOME-fork).
#
# Exit-code mapping (deliberate, W104-aware): the watcher's 1 (WARN) and
# 2 (CRIT) mean "threshold crossed AND the Telegram alert was already
# dispatched and verdict-verified by the watcher itself" — that is the job
# WORKING, not failing, so the cron receipt stays ok (otherwise every
# legitimate warning would also fire a redundant cron-fail P0). Only 4
# (CANNOT-MEASURE: no log readable / CANNOT-DELIVER: alert reached nobody)
# and unexpected codes propagate, so cron-runner's own alert covers exactly
# the states where the watcher could NOT speak for itself.
set -uo pipefail

REPO="/Users/nuzantara/nuzantara"
WATCHER="$REPO/scripts/qwen_quota_watch.py"

if [ ! -f "$WATCHER" ]; then
    echo "qwen_quota_watch_cron: watcher not found at $WATCHER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

/usr/bin/env python3 "$WATCHER" --hosts mini,air --alert
rc=$?
echo "qwen_quota_watch_cron: watcher rc=$rc" >&2
case "$rc" in
    0|1|2) exit 0 ;;
    *) exit "$rc" ;;
esac
