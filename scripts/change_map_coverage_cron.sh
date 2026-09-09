#!/usr/bin/env bash
# change_map_coverage_cron.sh — cron payload delivering
# scripts/ci/change_map_coverage.py's weekly report to the fleet mailbox.
#
# Same shape as scripts/queue_stall_notify_cron.sh: this is a REPORTER, not
# an actuator. change_map_coverage.py touches no allowlist, workflow file,
# or classifier rule — it only reads `gh run`/`gh api` output, writes a
# markdown file under docs/reports/change-map-coverage/, and fleet-mails a
# one-line summary via scripts/fleet_mail.sh (key `change-map-coverage:weekly`).
#
# Lives IN THE REPO; the crontab line points here directly, never a ~/scripts
# copy (superscar #1 HOME-fork).
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
# Weekly, Monday 03:00 WITA (= 19:00 UTC Sunday), intended for the Mini
# crontab (H24, has `gh` auth already provisioned for the sibling
# queue_stall_notify/queue_unstick family):
#
#   0 19 * * 0 /bin/bash /Users/nuzantara/nuzantara/scripts/change_map_coverage_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/change-map-coverage.log 2>&1
#
# No launchd plist for this family — follow queue_unstick_cron.sh's raw
# crontab precedent, not queue_shepherd's plist one.
#
# Kill switch (no crontab edit needed): export
# CHANGE_MAP_COVERAGE_ENABLED=false in the environment cron-runner runs
# under, or prefix the crontab line with it to disable in place.
#
# Prerequisites the conductor should verify before installing:
#   - `gh auth status` succeeds as a principal with repo READ access
#     (change_map_coverage.py shells out to `gh run list` / `gh run view` /
#     `gh api .../logs`; this wrapper itself makes no gh call).
#   - `scripts/fleet_mail.sh` reachable and its `pro` SSH target answers
#     BatchMode (see fleet_mail.sh header) — a silently-undelivered weekly
#     summary is exactly the kind of mute-cron regression superscar #2
#     exists to catch.
#
# REPO PATH — derived from this script's own location (same discipline as
# queue_unstick_cron.sh / queue_stall_notify_cron.sh): the checkout path
# differs per machine, so a hardcoded path is a machine-specific landmine.
#
# Exit-code mapping: change_map_coverage.py's 0 (report written + mail sent,
# or --no-mail/dry-run success) is the only "ok" state for cron-runner's
# receipt. Non-zero (fetch failure serious enough to abort, or a fleet-mail
# send failure) propagates as a real failure, so cron-runner's alert_failure
# fires and the receipt records last_error.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORTER="$REPO/scripts/ci/change_map_coverage.py"

if [ "${CHANGE_MAP_COVERAGE_ENABLED:-true}" = "false" ]; then
    echo "change_map_coverage_cron: disabled via CHANGE_MAP_COVERAGE_ENABLED=false" >&2
    exit 0
fi

if [ ! -f "$REPORTER" ]; then
    echo "change_map_coverage_cron: reporter not found at $REPORTER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

cd "$REPO" || exit 67

/usr/bin/env python3 "$REPORTER" --days 7
rc=$?
echo "change_map_coverage_cron: reporter rc=$rc" >&2
exit "$rc"
