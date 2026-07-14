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
# Exception: newsletter_cli.py runs entirely INSIDE Fly (see step 1.5) —
# DATABASE_URL, NOTIFICATIONS_API_KEY, and the notifications endpoint only
# exist there; Pro is just the scheduler.
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

# 1.5 Newsletter only: dispatch the WHOLE run inside the Fly `api` process
# instead of requiring local Postgres + pg-proxy. DATABASE_URL,
# NOTIFICATIONS_API_KEY, and the /api/notifications/send-email endpoint all
# live only on Fly — Pro has none of them and per CLAUDE.md §Cost constraint
# a secret is never duplicated to a new machine "to make a cron simpler".
# `fly` (FLY_API_TOKEN) is already present on Pro for other ops, so this adds
# zero new secrets. `-g api` targets the process group by name (never a raw
# machine ID, which is not stable across deploys/restarts).
if [[ "$MODULE" == "backend.services.newsletter.newsletter_cli" ]]; then
    if ! command -v fly >/dev/null 2>&1; then
        echo "[wr2-wrapper] ERROR: fly CLI not found on PATH — cannot dispatch newsletter_cli into Fly (api process)." >&2
        exit 74
    fi
    remote_cmd="python -m $MODULE"
    for arg in "$@"; do
        remote_cmd+=" $(printf '%q' "$arg")"
    done
    if [[ -n "${NEWSLETTER_SUBJECT_PREFIX:-}" ]]; then
        remote_cmd="NEWSLETTER_SUBJECT_PREFIX=$(printf '%q' "$NEWSLETTER_SUBJECT_PREFIX") $remote_cmd"
    fi
    exec fly ssh console -a nuzantara-rag -g api -C "$remote_cmd"
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

# 3.5 Measurer only: keep the IG long-lived token alive before the sweep
# (Task-30 watchdog, runbook docs/runbooks/ig-token-watchdog.md §Arming).
# Token-tolerant: with no token configured the watchdog exits 2 and the
# scheduler still runs (it degrades to "no samplers" on its own); the exit-2
# line below is the standing NEEDS-OPERATOR alarm until a token lands.
if [[ "$MODULE" == "backend.services.measurer.scheduler_cli" ]]; then
    set +e
    IG_TOKEN_ENV_FILE="$SECRETS_FILE" \
    IG_TOKEN_STATE_FILE="$HOME/.nuzantara-ig-token-state.json" \
    PYTHONPATH=. "$VENV_PY" -m backend.services.measurer.ig_token_watchdog
    wd_rc=$?
    set -e
    if [[ $wd_rc -eq 1 || $wd_rc -eq 2 ]]; then
        # exit 1 = no token in env at all; exit 2 = refresh needs the operator.
        # Both are the standing starvation alarm, proven live 2026-07-13.
        echo "[measurer] ig-token-watchdog NEEDS OPERATOR (exit $wd_rc — token missing or unrefreshable)" >&2
    elif [[ $wd_rc -ne 0 ]]; then
        echo "[measurer] ig-token-watchdog unexpected exit $wd_rc" >&2
    fi
    # Re-source so a just-refreshed token reaches scheduler_cli.
    if [[ -f "$SECRETS_FILE" ]]; then
        # shellcheck disable=SC1090
        set -a
        source "$SECRETS_FILE"
        set +a
    fi
fi

exec env PYTHONPATH=. "$VENV_PY" -m "$MODULE" "$@"
