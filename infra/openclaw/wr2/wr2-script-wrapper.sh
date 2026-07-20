#!/bin/bash
# wr2-script-wrapper.sh — runs a standalone scripts/wr2_*.py script
# (not a backend module). Complements wr2-cron-wrapper.sh (which is for
# `python -m backend.xxx` modules).
#
# Usage (from a plist):
#   <array>
#     <string>/Users/nuzantara/.openclaw/bin/wr2/wr2-script-wrapper.sh</string>
#     <string>scripts/wr2_image_generator.py</string>
#     <string>--arg1</string>
#   </array>
#
# Responsibilities:
#   1. Source ~/.nuzantara-secrets.env for Telegram + AWS Tigris + misc
#   2. Resolve DATABASE_URL from DATABASE_URL_LOCAL (requires pg-proxy)
#   3. cd into repo root, activate apps/backend-rag/.venv, exec python <script>
#
# Fails loud (non-zero exit) on any missing piece.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <script-relative-path> [args...]" >&2
    exit 64
fi

SCRIPT_PATH="$1"
shift

# 2026-05-06: switched from ~/nuzantara (multi-agent collision zone)
# to dedicated git worktree ~/nuzantara-deploy on branch deploy/main.
# The main repo at ~/nuzantara is shared by 3+ Claude/Codex sessions
# that toggle branches every 1-3 min — production cron must read from a stable
# worktree pinned to origin/main, never feature branches.
# To update: `cd ~/nuzantara-deploy && git pull origin main`.
REPO_ROOT="${WR2_REPO_ROOT:-${HOME}/nuzantara-deploy}"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"

# 1. Secrets — source primary then backend-specific (additive)
if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$SECRETS_FILE"
    set +a
fi

# 1b. Backend-specific secrets (JWT_SECRET_KEY, OPENAI_API_KEY, API_KEYS)
# These are required by apps/backend-rag/backend/app/core/config.py
# Pydantic Settings validators. Without them, scripts importing backend
# modules emit WARNINGs and fall back to noop config (no LLM cost
# recorder, no auth checks).
BACKEND_SECRETS_FILE="${HOME}/.nuzantara-backend-secrets.env"
if [[ -f "$BACKEND_SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$BACKEND_SECRETS_FILE"
    set +a
fi

# 2. DATABASE_URL — FORCE-override to LOCAL (pg-proxy on 127.0.0.1:15432).
# Why: ~/.nuzantara-secrets.env defines DATABASE_URL=postgres://...@nuzantara-postgres.flycast
# (Fly 6PN internal hostname — only resolves *inside* Fly). When sourced on Pro,
# DATABASE_URL is set but unusable; supervisor would emit "errno 8 nodename nor
# servname" forever. Always pin DATABASE_URL_LOCAL on Pro/Mini regardless of
# whatever the secrets file pre-set. Bug discovered 2026-05-06 (supervisor in
# reconnect-loop since 2026-04-30 17:31).
if [[ -z "${DATABASE_URL_LOCAL:-}" ]]; then
    echo "[wr2-script-wrapper] ERROR: DATABASE_URL_LOCAL not set in $SECRETS_FILE" >&2
    exit 74
fi
DATABASE_URL="$DATABASE_URL_LOCAL"
export DATABASE_URL

# Sanity check: pg-proxy listening?
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
    echo "[wr2-script-wrapper] ERROR: 127.0.0.1:15432 unreachable (is com.balizero.wr2.pg-proxy loaded?)" >&2
    exit 74
fi

# 3. Resolve script path
FULL_SCRIPT="$REPO_ROOT/$SCRIPT_PATH"
if [[ ! -f "$FULL_SCRIPT" ]]; then
    echo "[wr2-script-wrapper] ERROR: script not found: $FULL_SCRIPT" >&2
    exit 66
fi

# 4. Repo + venv + exec
cd "$REPO_ROOT"
VENV_DIR="$REPO_ROOT/apps/backend-rag/.venv"
VENV_PY="$VENV_DIR/bin/python"
REQ_FILE="$REPO_ROOT/apps/backend-rag/requirements-prod.txt"

# W81b (2026-06-23): the old preflight only checked that the venv PYTHON exists
# (`-x`). But a venv-SKELETON — python present, site-packages evaporated by a
# deploy-worktree re-add — passed that check and crashed at `import asyncpg`
# (ModuleNotFoundError, supervisor down ~3 days, 20→23 Jun). Probe the real import.
VENV_BROKEN=0
if [[ -x "$VENV_PY" ]]; then
    "$VENV_PY" -c "import asyncpg" >/dev/null 2>&1 || VENV_BROKEN=1
fi

# Venv-preflight (Wave 1 fix 2026-05-19, 4-LLM panel synthesis 3/3 quorum):
# A missing venv on the deploy worktree caused the WR2 supervisor to
# crashloop silently for 84h (2026-05-16 03:32 → 2026-05-19 09:44),
# accumulating 27,227 error lines in `wr2_supervisor_watchdog.launchd.err.log`
# and 1.2 MB in `wr2_supervisor.launchd.err.log`. The events_outbox
# design saved us from data loss (7 missed `wr2_status_change` events
# auto-replayed on recovery), but 4 days of pipeline downtime are
# unacceptable for a solo-dev operation.
#
# Mitigation: auto-heal + Telegram alert IN THIS WRAPPER.
# Flow:
#   - If venv exists: fast-path exec (zero overhead).
#   - If venv missing: alert Telegram (cooldown 1h), attempt auto-heal
#     via `python -m venv` + `pip install -r requirements-prod.txt`
#     (3-5 min). If auto-heal fails: hard exit 75 (same as before,
#     preserves audit trail + KeepAlive restart cycle).
#
# Reference: research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md
if [[ ! -x "$VENV_PY" || "$VENV_BROKEN" == "1" ]]; then
    NOW=$(date '+%Y-%m-%d %H:%M:%S WITA')
    echo "[wr2-script-wrapper] WARN ${NOW}: venv Python missing at $VENV_PY — attempting auto-heal" >&2

    # Telegram alert (cooldown 1h via state file to avoid spam)
    ALERT_STATE="${HOME}/.agent/decisions/state/wr2_venv_alert.state"
    NOW_TS=$(date +%s)
    LAST_TS=$(cat "$ALERT_STATE" 2>/dev/null || echo 0)
    COOLDOWN_SEC=3600  # 1h between repeat alerts
    if (( NOW_TS - LAST_TS > COOLDOWN_SEC )); then
        if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]]; then
            curl -sS --max-time 5 \
                "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
                -d text="🚨 WR2 venv missing at ${VENV_DIR} — auto-heal attempted at ${NOW}" \
                >/dev/null 2>&1 || true
        fi
        mkdir -p "$(dirname "$ALERT_STATE")"
        echo "$NOW_TS" > "$ALERT_STATE"
    fi

    # Auto-heal: create venv + pip install
    PYENV_PY311="${HOME}/.pyenv/versions/3.11.11/bin/python"
    if [[ ! -x "$PYENV_PY311" ]]; then
        echo "[wr2-script-wrapper] ERROR: pyenv Python 3.11.11 not found at $PYENV_PY311" >&2
        exit 75
    fi

    if "$PYENV_PY311" -m venv "$VENV_DIR" 2>&1; then
        echo "[wr2-script-wrapper] auto-heal: venv created at $VENV_DIR" >&2
        if [[ ! -f "$REQ_FILE" ]]; then
            echo "[wr2-script-wrapper] ERROR: requirements-prod.txt not found at $REQ_FILE" >&2
            exit 75
        fi
        echo "[wr2-script-wrapper] auto-heal: installing $REQ_FILE (this may take 3-5 min)" >&2
        if "$VENV_PY" -m pip install --quiet --upgrade pip >&2 \
           && "$VENV_PY" -m pip install --quiet -r "$REQ_FILE" >&2; then
            echo "[wr2-script-wrapper] auto-heal: pip install completed, resuming exec" >&2
        else
            echo "[wr2-script-wrapper] ERROR: auto-heal pip install failed — manual fix required" >&2
            exit 75
        fi
    else
        echo "[wr2-script-wrapper] ERROR: auto-heal venv creation failed — manual fix required" >&2
        exit 75
    fi
fi

exec "$VENV_PY" "$FULL_SCRIPT" "$@"
