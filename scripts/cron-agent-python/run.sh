#!/usr/bin/env bash
# Cron wrapper for cron-agent-python jobs.
# Usage: run.sh <job-name>
# Ensures:
#   - Minimal PATH (homebrew, pyenv, local bin)
#   - Secrets sourced from ~/.zshrc.secrets (TELEGRAM_BOT_TOKEN etc.)
#   - No ANTHROPIC_API_KEY leaked (OAuth Max plan only, $0)
#   - venv Python used
set -uo pipefail

JOB="${1:?usage: run.sh <job-name>}"
SCRIPT_DIR="/Users/nuzantara/scripts/cron-agent-python"
VENV_PY="/Users/nuzantara/scripts/cron-agent-venv/bin/python"
SCRIPT="$SCRIPT_DIR/${JOB//-/_}.py"

if [[ ! -f "$SCRIPT" ]]; then
    echo "ERROR: script not found: $SCRIPT" >&2
    exit 127
fi

export PATH="/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/Users/nuzantara/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/Users/nuzantara"
export USER="nuzantara"

# Source secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID, GITHUB_TOKEN, …).
# cron runs with a clean env — without this, agent_job.py falls back to
# `reason=no_token` and the job "succeeds" silently without ever paging.
# `set -a` exports every variable the sourced file assigns; the unset of
# ANTHROPIC_API_KEY below must happen AFTER sourcing, so even if the secrets
# file defines it the paid-API-key kill-switch still wins.
if [[ -f "$HOME/.zshrc.secrets" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.zshrc.secrets"
    set +a
fi

# Redis on this host requires AUTH (password added ~2026-06-29), but every
# `redis-cli` call in this tree invokes the bare binary with no credentials.
# redis-cli then answers NOAUTH and prints nothing on stdout, which callers
# read as "key absent" — so the cron:reports event bus silently stopped
# publishing and the log-anomaly dedup failed OPEN (288 spurious Telegram
# alerts/day). REDIS_PASSWORD lives in ~/.nuzantara-secrets.env, NOT in
# ~/.zshrc.secrets sourced above. Pass it via REDISCLI_AUTH — redis-cli reads
# that natively — instead of `-a`, so the secret never lands in argv/`ps`.
# Extracted in a SUBSHELL so nothing else from that file leaks into the job env
# (in particular ANTHROPIC_API_KEY, killed below, must stay killed).
if [[ -z "${REDISCLI_AUTH:-}" && -f "$HOME/.nuzantara-secrets.env" ]]; then
    _redis_pw="$(set -a; source "$HOME/.nuzantara-secrets.env" >/dev/null 2>&1; printf '%s' "${REDIS_PASSWORD:-}")"
    if [[ -n "$_redis_pw" ]]; then
        export REDISCLI_AUTH="$_redis_pw"
    fi
    unset _redis_pw
fi

# Force clean auth env (prevent accidental pay-per-token) — MUST run after
# sourcing secrets so the kill-switch has the last word.
unset ANTHROPIC_API_KEY

exec "$VENV_PY" "$SCRIPT"
