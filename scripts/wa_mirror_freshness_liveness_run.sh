#!/usr/bin/env bash
# wa_mirror_freshness_liveness_run.sh — venv-python launcher for
# scripts/wa_mirror_freshness_liveness.py.
#
# Same shape and rationale as scripts/intake_health_report_run.sh (see that
# file's header for the full HOME-fork / kill-switch / heartbeat design
# note) — REPO_ROOT derived from this file's own location, kill switch
# honored here with its OWN disabled-heartbeat before exiting, enabled path
# execs straight into the venv python which owns the real per-run heartbeat
# and the freshness/liveness check itself.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORGAN_ID="pro.wa_mirror_freshness_liveness"

# shellcheck source=scripts/lib/heartbeat.sh
source "$REPO_ROOT/scripts/lib/heartbeat.sh"

if [ "${WA_MIRROR_FRESHNESS_LIVENESS_ENABLED:-true}" = "false" ]; then
  organism_heartbeat "$ORGAN_ID" "disabled" "WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=false"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=false — skipping run"
  exit 0
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
exec "$PYBIN" -u "$REPO_ROOT/scripts/wa_mirror_freshness_liveness.py" "$@"
