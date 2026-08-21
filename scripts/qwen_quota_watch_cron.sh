#!/usr/bin/env bash
# qwen_quota_watch_cron.sh — cron payload for cron-runner.sh (daily; deployed
# on Mini as of 2026-08-21 — Pro's ssh shell lacks Full Disk Access, so a
# crontab write there fails EPERM; TCC, not Unix permissions).
#
# cron-runner executes payloads with /bin/bash, so the python watcher needs
# this thin wrapper. It lives IN THE REPO and the crontab line points here
# directly (never a ~/scripts copy — superscar #1 HOME-fork).
#
# Deliberately does NOT pass --hosts: the watcher's own default
# ("pro,mini,air") already self-skips whichever host it is running ON
# (qwen_quota_watch.py main(), "skip the alias that is THIS machine"), so the
# union always covers exactly the 3 hosts regardless of which machine
# cron-runner executes this on. An earlier revision hardcoded --hosts
# mini,air (correct only when executed FROM Pro, where local=pro completes
# the union) — moving the cron to Mini made local=mini, and Pro was then
# silently omitted: not even flagged MISSED, since it was never queried at
# all. Caught 2026-08-21 by comparing a live run's total against a
# known-good cross-host figure before arming this cron on the new host.
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

/usr/bin/env python3 "$WATCHER" --alert
rc=$?
echo "qwen_quota_watch_cron: watcher rc=$rc" >&2
case "$rc" in
    0|1|2) exit 0 ;;
    *) exit "$rc" ;;
esac
