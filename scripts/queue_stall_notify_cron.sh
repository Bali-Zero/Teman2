#!/usr/bin/env bash
# queue_stall_notify_cron.sh — cron payload for cron-runner.sh, delivering
# scripts/queue_stall_classifier.py's findings to the fleet mailbox via
# scripts/queue_stall_notify.py.
#
# cron-runner executes payloads with /bin/bash, so the python notifier needs
# this thin wrapper. It lives IN THE REPO and the crontab line points here
# directly (never a ~/scripts copy — superscar #1 HOME-fork).
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
# This is a REPORTER, not an actuator: queue_stall_classifier.py never
# mutates a PR (its own AST self-check enforces that), and neither does this
# wrapper's payload — it only reads the classifier's report and fleet-mails
# it. A slower cadence than queue_unstick_cron.sh's 10 minutes is therefore
# appropriate: */30, matching queue_stall_classifier.py's own
# DEFAULT_MIN_AGE_MINUTES=30 — running more often than the classifier's own
# age floor would just re-examine the same PRs before anything about them
# could plausibly have changed.
#
#   */30 * * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/queue_stall_notify_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/queue-stall-notify.log 2>&1
#
# No launchd plist exists for this family, and none should be invented here:
# the sibling queue_unstick_cron.sh runs from a raw crontab line on Mini
# (verified live), and queue_shepherd is the one member of this family that
# is plist-driven. Follow queue_unstick's precedent, not queue_shepherd's.
#
# Kill switch (no crontab edit needed): export
# QUEUE_STALL_NOTIFY_ENABLED=false in the environment cron-runner.sh runs
# under, or wrap the crontab line with `QUEUE_STALL_NOTIFY_ENABLED=false
# /bin/bash ...` to disable in place.
#
# Prerequisites the conductor should verify before installing:
#   - `gh auth status` succeeds as a principal with repo READ access (the
#     classifier subprocess needs it; this wrapper itself makes no gh call
#     and neither does queue_stall_notify.py outside that subprocess).
#   - `scripts/fleet_mail.sh` reachable and its `pro` SSH target answers
#     BatchMode (see fleet_mail.sh header) — a stall signal silently failing
#     to send is exactly the kind of mute-cron regression superscar #2
#     exists to catch; queue_stall_notify.py's own summary line reports
#     send_failed>0 when this happens, but only if something reads the log.
#
# REPO PATH — derived from this script's own location (same discipline as
# queue_unstick_cron.sh / qwen_quota_watch_cron.sh): the checkout path
# differs per machine, so a hardcoded path is a machine-specific landmine.
#
# Exit-code mapping: queue_stall_notify.py's 0 (ran clean, whether or not it
# found/delivered any stalls) is the only "ok" state for cron-runner's
# receipt. Non-zero (the classifier itself failed, OR a fleet-mail send
# failed) propagates as a real failure, so cron-runner's alert_failure fires
# and the receipt records last_error — a gh/network hiccup here must be
# loud, never a silent "nothing was stuck" (superscar #2/#9).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
NOTIFIER="$REPO/scripts/queue_stall_notify.py"

if [ ! -f "$NOTIFIER" ]; then
    echo "queue_stall_notify_cron: notifier not found at $NOTIFIER (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

/usr/bin/env python3 "$NOTIFIER"
rc=$?
echo "queue_stall_notify_cron: notifier rc=$rc" >&2
exit "$rc"
