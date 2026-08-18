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

# Case-insensitive, and matching the Python side's superset (0|false|no) —
# verbale #10a: the literal-"false"-only match let WA_MIRROR_FRESHNESS_
# LIVENESS_ENABLED=0 / =No slip past the wrapper into an interpreter spawn
# that the Python script itself then correctly no-oped on (Python does
# `.strip().lower() in ("0", "false", "no")`), so this was a wasted spawn
# rather than a real bypass — but a wrapper that disagrees with the script
# it launches about what "disabled" means is worth closing regardless.
_wa_freshness_enabled_lc="$(printf '%s' "${WA_MIRROR_FRESHNESS_LIVENESS_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
case "$_wa_freshness_enabled_lc" in
  false|0|no)
    organism_heartbeat "$ORGAN_ID" "disabled" "WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=$WA_MIRROR_FRESHNESS_LIVENESS_ENABLED"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=$WA_MIRROR_FRESHNESS_LIVENESS_ENABLED — skipping run"
    exit 0
    ;;
esac

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
exec "$PYBIN" -u "$REPO_ROOT/scripts/wa_mirror_freshness_liveness.py" "$@"
