#!/usr/bin/env bash
# intake_health_report_run.sh — venv-python launcher for scripts/intake_health_report.py.
#
# W0 read-only guardian wrapper, same shape as every sibling intake launchd
# wrapper (com.nuzantara.intake-gate-count-pusher / intake-blob-retention /
# intake-review-reader{,-liveness}): launchd always spawns a `/bin/bash
# <this>.sh`, never a venv python directly — this IS the resolve-python
# convention for this corner.
#
# REPO_ROOT is derived from this file's OWN location (superscar #1 HOME-fork
# discipline: never hardcode a path that could silently diverge from where
# this script actually lives — Pro `/Users/nuzantara/nuzantara`, Air-M5
# `/Users/balizero/nuzantara`), rather than a literal per-machine string.
#
# Kill switch INTAKE_HEALTH_REPORT_ENABLED (default true): honored HERE, not
# only inside the Python script, so a disabled organ never even spawns the
# interpreter — and the disabled path writes its OWN final heartbeat before
# exiting (organism gene G2xG5: "wrapper honors X_ENABLED=false AND writes a
# final heartbeat status=disabled before exiting"). The enabled path execs
# straight into the venv python, which owns the real per-run heartbeat
# (~/.organism/last_seen/pro.intake_health_report.json) and the report
# itself — this wrapper's only job is safe launch, nothing decorative.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORGAN_ID="pro.intake_health_report"

# shellcheck source=scripts/lib/heartbeat.sh
source "$REPO_ROOT/scripts/lib/heartbeat.sh"

# Case-insensitive, and matching the Python side's superset (0|false|no) —
# verbale #10a: see wa_mirror_freshness_liveness_run.sh's twin comment.
_intake_health_enabled_lc="$(printf '%s' "${INTAKE_HEALTH_REPORT_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
case "$_intake_health_enabled_lc" in
  false|0|no)
    organism_heartbeat "$ORGAN_ID" "disabled" "INTAKE_HEALTH_REPORT_ENABLED=$INTAKE_HEALTH_REPORT_ENABLED"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INTAKE_HEALTH_REPORT_ENABLED=$INTAKE_HEALTH_REPORT_ENABLED — skipping run"
    exit 0
    ;;
esac

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
exec "$PYBIN" -u "$REPO_ROOT/scripts/intake_health_report.py" "$@"
