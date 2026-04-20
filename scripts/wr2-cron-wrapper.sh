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
# Preferred: DATABASE_URL_LOCAL from secrets file, pointing at localhost
# (the com.balizero.wr2.pg-proxy LaunchAgent keeps `fly proxy 15432:5432
# -a nuzantara-postgres` alive). This avoids spinning a Fly SSH VM on
# every cron tick.
if [[ -z "${DATABASE_URL:-}" ]]; then
    if [[ -n "${DATABASE_URL_LOCAL:-}" ]]; then
        DATABASE_URL="$DATABASE_URL_LOCAL"
    else
        echo "[wr2-wrapper] ERROR: DATABASE_URL_LOCAL not set in $SECRETS_FILE. Add it (e.g. postgres://user:pass@localhost:5432/db) and load com.balizero.wr2.pg-proxy first." >&2
        exit 74
    fi
    export DATABASE_URL
fi

# Sanity: fail fast if localhost:15432 is unreachable (pg-proxy down)
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
    echo "[wr2-wrapper] ERROR: cannot reach 127.0.0.1:15432 — is com.balizero.wr2.pg-proxy loaded? (launchctl list | grep pg-proxy)" >&2
    exit 74
fi

# 3. Repo + venv + exec
cd "$REPO_ROOT/apps/backend-rag"
if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    # Fall back to pyenv 3.11.11 shim so cron still runs if .venv is missing
    export PATH="$HOME/.pyenv/versions/3.11.11/bin:$PATH"
fi

exec env PYTHONPATH=. python -m "$MODULE" "$@"
