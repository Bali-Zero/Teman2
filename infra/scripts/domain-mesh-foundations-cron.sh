#!/bin/bash
# Domain mesh Phase 0 — daily 04:00 WITA gov-apis health probe.
#
# Wave 2 review fix (Codex W2 + DeepSeek W2, 2026-05-08):
# - Use absolute venv python (was: source 2>/dev/null = silent fail)
# - Atomic snapshot via tmp + mv (was: > redirect = partial file on crash)
# - Kill-switch via FOUNDATIONS_CRON_ENABLED env var
# - Read snapshot via env var (was: shell-quote interpolation in python -c)
set -uo pipefail

# Kill switch: set FOUNDATIONS_CRON_ENABLED=false to disable without
# unloading the LaunchAgent.
if [ "${FOUNDATIONS_CRON_ENABLED:-true}" = "false" ]; then
    echo "$(date) foundations cron disabled via FOUNDATIONS_CRON_ENABLED=false" >&2
    exit 0
fi

LOG_DIR="$HOME/logs/domain-mesh-foundations"
SNAPSHOT_DIR="$HOME/.cache/domain-mesh-foundations/snapshots"
mkdir -p "$LOG_DIR" "$SNAPSHOT_DIR"

LOG_FILE="$LOG_DIR/foundations-daily-$(date +%Y%m%d).log"
SNAPSHOT_FILE="$SNAPSHOT_DIR/gov-apis-health-$(date +%Y%m%d).json"
SNAPSHOT_TMP="${SNAPSHOT_FILE}.tmp.$$"

REPO_ROOT="${HOME}/Desktop/nuzantara"
cd "$REPO_ROOT/apps/mata-garuda" || {
    echo "$(date) FAILED: cannot cd to $REPO_ROOT/apps/mata-garuda" >> "$LOG_FILE"
    exit 1
}

# Use absolute venv python — fail loud if it's missing instead of silently
# falling back to system python (which violates the no-system-python rule
# in CLAUDE.md and crashes opaquely on missing deps).
VENV_PY="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo "$(date) FAILED: venv python not executable at $VENV_PY" >> "$LOG_FILE"
    exit 2
fi

# Write to .tmp file first, then mv atomically only on success.
"$VENV_PY" -c "
import asyncio, json, sys
# Lazy direct import — avoids pulling transformers/torch via foundations/__init__.py.
from mata_garuda.foundations.gov_apis_health import probe_inventory
report = asyncio.run(probe_inventory())
data = {
    'total': report.total,
    'operational': report.operational,
    'results': [r.__dict__ for r in report.results],
}
sys.stdout.write(json.dumps(data, indent=2))
" > "$SNAPSHOT_TMP" 2>>"$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    rm -f "$SNAPSHOT_TMP"
    echo "$(date) FAILED foundations daily probe (exit $EXIT_CODE)" >> "$LOG_FILE"
    exit $EXIT_CODE
fi

# Atomic publish: only rename to canonical path if Python succeeded.
mv "$SNAPSHOT_TMP" "$SNAPSHOT_FILE"

# Read counters via env var instead of shell-interpolating the path
# (avoids quote injection if SNAPSHOT_FILE ever picks up unexpected chars).
SUMMARY=$(SNAPSHOT_FILE="$SNAPSHOT_FILE" "$VENV_PY" -c "
import json, os
d = json.load(open(os.environ['SNAPSHOT_FILE']))
print(f\"{d['operational']}/{d['total']}\")
")
echo "$(date) gov-apis snapshot: $SUMMARY operational" >> "$LOG_FILE"

# TODO Phase 1: compare vs 7-day baseline + Telegram alert if drop > 10pp
exit 0
