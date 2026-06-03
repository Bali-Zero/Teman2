#!/bin/bash
# S3 / W55: weekly cron wrapper for the suppressed-alerts digest.
# Emits one Telegram summary of escalations hidden by the 4h cooldown in the
# last 7 days, then resets the per-job suppressed counters.
#
# Loaded via infra/launchd/com.nuzantara.escalations-digest.weekly.plist
# (Sunday 09:00 WITA — Pro only, the canonical node owning escalation_cooldown.json).
set -u

PYTHON="${PYTHON:-/usr/bin/env python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIGEST="${SCRIPT_DIR}/escalations_suppressed_digest.py"

if [ ! -f "$DIGEST" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ERROR: digest script not found: $DIGEST" >&2
    exit 2
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) escalations-digest: starting"
$PYTHON "$DIGEST"
RC=$?
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) escalations-digest: done (rc=$RC)"
exit "$RC"
