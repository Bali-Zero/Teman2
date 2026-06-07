#!/bin/bash
# wr2-cron-wrapper.sh — common entry point for every War Room 2.0 LaunchAgent.
#
# Usage:
#   wr2-cron-wrapper.sh <python module>
#
# Example (from a plist):
#   <array>
#     <string>/Users/nuzantara/Desktop/nuzantara/scripts/wr2-cron-wrapper.sh</string>
#     <string>backend.services.intel.trend_hunter.cli</string>
#   </array>
#
# Responsibilities:
#   1. Source ~/.nuzantara-secrets.env for Telegram + misc creds.
#   2. Resolve DATABASE_URL from Fly (nuzantara-rag) once per invocation.
#   3. cd into apps/backend-rag, activate venv, exec python -m <module>.
#
# Designed for macOS launchd (Pro). Fails loud (exit != 0) if any required
# piece is missing so missed-runs alerter can pick it up.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <python module>" >&2
    exit 64
fi

MODULE="$1"
shift

case "$MODULE" in
    backend.services.cognitive.connector_cli)
        ORGANISM_HB_ID="wr2.connector"
        ;;
    backend.services.intel.dossier_compiler_cli)
        ORGANISM_HB_ID="wr2.dossier_compiler"
        ;;
    backend.services.learner.learner_cli)
        ORGANISM_HB_ID="wr2.learner_nightly"
        ;;
    backend.services.measurer.scheduler_cli)
        ORGANISM_HB_ID="wr2.measurer"
        ;;
    backend.services.review.sla_worker_cli)
        ORGANISM_HB_ID="wr2.sla_worker"
        ;;
    backend.services.cognitive.strategos_cli)
        ORGANISM_HB_ID="wr2.strategos"
        ;;
    backend.services.intel.trend_hunter.cli)
        ORGANISM_HB_ID="wr2.trend_hunter"
        ;;
    backend.services.hardening.*)
        ORGANISM_HB_ID="wr2.hardening"
        ;;
    *)
        ORGANISM_HB_ID=""
        ;;
esac

HEARTBEAT_LIB="${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh"
if [[ -n "$ORGANISM_HB_ID" && -f "$HEARTBEAT_LIB" ]]; then
    # shellcheck disable=SC1090
    source "$HEARTBEAT_LIB"
    organism_heartbeat "$ORGANISM_HB_ID" "starting" "module=$MODULE"
    _organism_hb_finalize() {
        local rc=$?
        local status="ok"
        if [[ "$rc" -eq 1 ]]; then
            status="warning"
        elif [[ "$rc" -ne 0 ]]; then
            status="error"
        fi
        organism_heartbeat "$ORGANISM_HB_ID" "$status" "module=$MODULE rc=$rc"
    }
    trap _organism_hb_finalize EXIT
fi

REPO_ROOT="${NUZANTARA_REPO_ROOT:-$HOME/Desktop/nuzantara}"
SECRETS_FILE="${NUZANTARA_SECRETS:-$HOME/.nuzantara-secrets.env}"
LOG_DIR="${WR2_LOG_DIR:-$HOME/.openclaw/workspace/logs/war-room-v2}"
mkdir -p "$LOG_DIR"

# 1. Secrets
if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$SECRETS_FILE"
    set +a
fi

# 2. DATABASE_URL resolution
# Force DATABASE_URL_LOCAL on Pro/Mini. The shared secrets file may define
# DATABASE_URL with a Fly 6PN hostname; that only resolves inside Fly and makes
# launchd jobs fail locally with socket.gaierror.
if [[ -z "${DATABASE_URL_LOCAL:-}" ]]; then
    echo "[wr2-wrapper] ERROR: DATABASE_URL_LOCAL not set in $SECRETS_FILE. Add it (e.g. postgres://backend_rag_v2:<password>@127.0.0.1:15432/nuzantara_rag?sslmode=disable) and load com.balizero.wr2.pg-proxy first." >&2
    exit 74
fi
DATABASE_URL="$DATABASE_URL_LOCAL"
export DATABASE_URL

# Sanity: fail fast if localhost:15432 is unreachable (pg-proxy down)
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
    echo "[wr2-wrapper] ERROR: cannot reach 127.0.0.1:15432 — is com.balizero.wr2.pg-proxy loaded? (launchctl list | grep pg-proxy)" >&2
    exit 74
fi

# 3. Repo + venv + exec
cd "$REPO_ROOT/apps/backend-rag"
VENV_PY="$PWD/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
    # Fall back to pyenv 3.11.11 shim so cron still runs if .venv is missing
    export PATH="$HOME/.pyenv/versions/3.11.11/bin:$PATH"
    VENV_PY="python"
fi

set +e
env PYTHONPATH=. "$VENV_PY" -m "$MODULE" "$@"
rc=$?
set -e
exit "$rc"
