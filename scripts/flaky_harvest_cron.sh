#!/usr/bin/env bash
# flaky_harvest_cron.sh — cron payload for cron-runner.sh, running
# scripts/ci/flaky_harvest.py's MEASURE-ONLY comparison of pull_request vs merge_group job
# conclusions on tests.yml and delivering the headline numbers to the fleet mailbox.
#
# cron-runner executes payloads with /bin/bash, so the python harvester needs this thin wrapper.
# It lives IN THE REPO and the crontab line points here directly (never a ~/scripts copy —
# superscar #1 HOME-fork).
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
# This is a REPORTER, not an actuator: flaky_harvest.py never quarantines, skips, or disables a
# test, and neither does this wrapper — it only reads `gh run list`/`gh run view`/`gh api
# .../logs` and renders a report. Weekly cadence (Monday 03:30 WITA) matches the mandate's
# "weekly cron wrapper" spec and this workflow's own 7-day scan window — running more often than
# the window it scans would just re-measure runs already covered by the previous harvest.
#
#   30 3 * * 1 /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/flaky_harvest_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/flaky-harvest.log 2>&1
#
# No launchd plist exists for this family, and none should be invented here: follow
# queue_stall_notify_cron.sh's raw-crontab precedent, not queue_shepherd's plist one.
#
# Kill switch (no crontab edit needed): export FLAKY_HARVEST_ENABLED=false in the environment
# cron-runner.sh runs under, or wrap the crontab line with
# `FLAKY_HARVEST_ENABLED=false /bin/bash ...` to disable in place.
#
# Prerequisites the conductor should verify before installing:
#   - `gh auth status` succeeds as a principal with repo READ access on Bali-Zero/Teman2 (the
#     harvester's `gh run list`/`gh run view`/`gh api .../logs` calls need it).
#   - `scripts/fleet_mail.sh` reachable and its `pro` SSH target answers BatchMode (see
#     fleet_mail.sh header) — flaky_harvest.py's own stderr line reports "mailbox FAILED" when
#     this happens, but only if something reads the log (superscar #2).
#
# REPO PATH — derived from this script's own location (same discipline as
# queue_stall_notify_cron.sh / queue_unstick_cron.sh): the checkout path differs per machine, so
# a hardcoded path is a machine-specific landmine.
#
# Exit-code mapping: flaky_harvest.py's 0 (ran clean, whether or not any candidate was found, and
# whether or not the mailbox send itself succeeded — the harvester logs mailbox failures to
# stderr but does not fail the run on them, mirroring "a stall/flake report existing already
# helped even if paging failed") is the only "ok" state for cron-runner's receipt. Non-zero (the
# initial `gh run list` fetch itself failed) propagates as a real failure, so cron-runner's
# alert_failure fires and the receipt records last_error — a gh/network hiccup here must be
# loud, never a silent "nothing to report" (superscar #2/#9).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
HARVESTER="$REPO/scripts/ci/flaky_harvest.py"

if [ "${FLAKY_HARVEST_ENABLED:-true}" = "false" ] || [ "${FLAKY_HARVEST_ENABLED:-true}" = "0" ]; then
    echo "flaky_harvest_cron: disabled via FLAKY_HARVEST_ENABLED, no-op" >&2
    exit 0
fi

if [ ! -f "$HARVESTER" ]; then
    echo "flaky_harvest_cron: harvester not found at $HARVESTER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

/usr/bin/env python3 "$HARVESTER"
rc=$?
echo "flaky_harvest_cron: harvester rc=$rc" >&2
exit "$rc"
