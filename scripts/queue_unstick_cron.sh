#!/usr/bin/env bash
# queue_unstick_cron.sh — cron payload for cron-runner.sh (Mini, every 10 min).
#
# cron-runner executes payloads with /bin/bash, so the python unsticker needs
# this thin wrapper. It lives IN THE REPO and the crontab line points here
# directly (never a ~/scripts copy — superscar #1 HOME-fork).
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
# Every 10 minutes, via cron-runner.sh, matching the existing Mini pattern
# (compare: the qwen-quota-watch line already in `crontab -l`):
#
#   */10 * * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/queue_unstick_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/queue-unstick.log 2>&1
#
# Kill switch (no crontab edit needed): export QUEUE_UNSTICK_ENABLED=false
# in the environment cron-runner.sh runs under, or wrap the crontab line
# with `QUEUE_UNSTICK_ENABLED=false /bin/bash ...` to disable in place.
#
# Prerequisites the conductor should verify before installing:
#   - `gh auth status` succeeds as a principal with repo write access
#     (needed for `gh pr update-branch`) under the cron's env/PATH.
#   - `scripts/fleet_mail.sh` reachable and its `pro` SSH target answers
#     BatchMode (see fleet_mail.sh header) — a DIRTY signal silently
#     failing to send is exactly the kind of mute-cron regression
#     superscar #2 exists to catch; queue_unstick.py's own summary line
#     reports dirty_signal_failed>0 when this happens, but only if
#     something reads the log.
#
# REPO PATH — derived from this script's own location (same discipline as
# qwen_quota_watch_cron.sh): the checkout path differs per machine, so a
# hardcoded path is a machine-specific landmine.
#
# Exit-code mapping: queue_unstick.py's 0 (ran, whether or not it acted) is
# the only "ok" state for cron-runner's receipt. 4 (CANNOT-VERIFY — the PR
# list itself could not be fetched) and 1 (an update-branch or fleet-mail
# signal actually failed) both propagate as real failures, so cron-runner's
# alert_failure fires and the DLQ-style receipt records last_error — a
# gh/network hiccup here must be loud, never a silent "nothing to do"
# (superscar #2/#9: gh api failing is CANNOT-VERIFY, not an empty PR list).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
UNSTICKER="$REPO/scripts/queue_unstick.py"

if [ ! -f "$UNSTICKER" ]; then
    echo "queue_unstick_cron: unsticker not found at $UNSTICKER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

/usr/bin/env python3 "$UNSTICKER"
rc=$?
echo "queue_unstick_cron: unsticker rc=$rc" >&2
exit "$rc"
