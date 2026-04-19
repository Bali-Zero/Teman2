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

# 2. DATABASE_URL from Fly if not already in env
if [[ -z "${DATABASE_URL:-}" ]]; then
    # fly ssh returns \r-terminated strings — strip
    DATABASE_URL="$(fly ssh console -a nuzantara-rag -C "printenv DATABASE_URL" 2>/dev/null | tr -d '\r' | tail -n1)"
    # nuzantara-postgres.flycast hostname is Fly-only. For Pro cron we need
    # the public/tunnel form. If the value contains flycast, fall back to
    # whatever DATABASE_URL_LOCAL provides (set in .nuzantara-secrets.env).
    if [[ "$DATABASE_URL" == *flycast* ]]; then
        if [[ -n "${DATABASE_URL_LOCAL:-}" ]]; then
            DATABASE_URL="$DATABASE_URL_LOCAL"
        else
            echo "[wr2-wrapper] ERROR: fly DATABASE_URL uses flycast (Fly-internal). Set DATABASE_URL_LOCAL (e.g. via fly proxy) in $SECRETS_FILE before enabling launchd agents." >&2
            exit 74
        fi
    fi
    export DATABASE_URL
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
