#!/usr/bin/env bash
# qwen_quota_watch_cron.sh — cron payload for cron-runner.sh (Mini, daily).
#
# cron-runner executes payloads with /bin/bash, so the python watcher needs
# this thin wrapper. It lives IN THE REPO and the crontab line points here
# directly (never a ~/scripts copy — superscar #1 HOME-fork).
#
# HOST LIST — pass ALL THREE aliases, never a hand-picked subset. The watcher
# already skips whichever alias names the machine it is running on (see
# qwen_quota_watch.py's local_host checks), so `pro,mini,air` yields full
# fleet coverage from ANY host. The first version of this file hardcoded
# `mini,air` because it was written for Pro, where that happens to be the
# complement; run on Mini the same list silently omitted Pro and reported
# 71,411,936 tokens against the true 79,556,338 — and reported it as a
# COMPLETE reading, because a host that is never in the list never appears
# in the "MISSED:" line either. A narrowed host list defeats the watcher's
# whole coverage contract, so it is derived, not chosen.
#
# REPO PATH — derived from this script's own location, because the checkout
# path differs per machine and Pro is mid-migration (its crontab still points
# mostly at the old Desktop-rooted checkout, a minority at the migrated one —
# superscar #1 HOME-fork drift) — a hardcoded path is a machine-specific
# landmine: the previous literal `/Users/nuzantara/nuzantara` was correct on
# Mini and exit-66 on the very host the header claimed it was for.
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
WATCHER="$REPO/scripts/qwen_quota_watch.py"

if [ ! -f "$WATCHER" ]; then
    echo "qwen_quota_watch_cron: watcher not found at $WATCHER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

/usr/bin/env python3 "$WATCHER" --hosts pro,mini,air --alert
rc=$?
echo "qwen_quota_watch_cron: watcher rc=$rc" >&2
case "$rc" in
    0|1|2) exit 0 ;;
    *) exit "$rc" ;;
esac
