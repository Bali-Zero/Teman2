#!/usr/bin/env bash
# llm_burn_alarm_run.sh — LaunchAgent wrapper for scripts/llm_burn_alarm.py.
#
# Mirrors scripts/cost_breaker_run.sh's wrapper convention exactly (same
# secrets-sourcing, same absolute-interpreter discipline, same
# RUNTIME_ROOT=~/nuzantara-deploy default): the alarm's Telegram send needs
# TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_CHAT_ID, which must NOT live in the
# plist (VADEMECUM: no secrets in plists). Source them here at run time.
#
# Interpreter is resolved ONCE, absolutely, before the job runs — never via
# PATH after sourcing an env file (W108: the wrapper that reports a failure
# must not itself be running on the interpreter that failure just broke).
#
# Kill-switch: LLM_BURN_ALARM_RUN_OFF=1

set -uo pipefail

if [[ "${LLM_BURN_ALARM_RUN_OFF:-0}" == "1" ]]; then
    echo "llm_burn_alarm_run: disabled via LLM_BURN_ALARM_RUN_OFF=1" >&2
    exit 0
fi

RUNTIME_ROOT="${LLM_BURN_ALARM_RUNTIME_ROOT:-$HOME/nuzantara-deploy}"
ALARM="$RUNTIME_ROOT/scripts/llm_burn_alarm.py"

if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_OWNER_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-}"

if [[ ! -f "$ALARM" ]]; then
    echo "llm_burn_alarm_run: FATAL — alarm not found at $ALARM" >&2
    exit 1
fi

# stdlib-only (subprocess/statistics/decimal/argparse) — no venv dependency,
# but keep the same interpreter convention as the other FASE-0 wrappers.
PY="$RUNTIME_ROOT/apps/backend-rag/.venv/bin/python"
[[ -x "$PY" ]] || PY="/opt/homebrew/bin/python3"
[[ -x "$PY" ]] || PY="python3"

exec "$PY" "$ALARM"
