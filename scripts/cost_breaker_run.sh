#!/usr/bin/env bash
# cost_breaker_run.sh — LaunchAgent wrapper for the P9 cost-breaker CLI.
#
# Why a wrapper (not a bare python ProgramArguments like the other FASE-0
# plists)? The breaker's STOP push needs TELEGRAM_BOT_TOKEN, which must NOT live
# in the plist (VADEMECUM: no secrets in plists; W65 scar: even plist .bak leaks
# are a P2-SECURITY). So we source it here from ~/.nuzantara-secrets.env at run
# time, and we point LLM_COST_JSONL_ROOT at the cost-ledger export dir that
# cost_ledger_export.py refreshes from the Fly PG ledger.
#
# RUNTIME HOME = the deploy worktree (~/nuzantara-deploy), the
# deploy-puller-refreshed checkout that carries the FASE-0 scripts (same
# convention as install_fase0_governance.sh).
#
# Kill-switch: COST_BREAKER_RUN_OFF=1

set -uo pipefail

if [[ "${COST_BREAKER_RUN_OFF:-0}" == "1" ]]; then
    echo "cost_breaker_run: disabled via COST_BREAKER_RUN_OFF=1" >&2
    exit 0
fi

RUNTIME_ROOT="${COST_BREAKER_RUNTIME_ROOT:-$HOME/nuzantara-deploy}"
BREAKER="$RUNTIME_ROOT/scripts/cost_breaker.py"

# Export dir the breaker reads (cost_ledger_export.py writes here). Default
# matches cost_ledger_export.py's default; overridable for tests.
export LLM_COST_JSONL_ROOT="${LLM_COST_JSONL_ROOT:-$HOME/.agent/cost-ledger}"

# Source the Telegram token (TELEGRAM_BOT_TOKEN) for the STOP push. NEVER
# hardcode it. Absent token = breaker logs "would have sent" and degrades
# gracefully (it never raises), so a missing secrets file is non-fatal.
if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"

if [[ ! -f "$BREAKER" ]]; then
    echo "cost_breaker_run: FATAL — breaker not found at $BREAKER" >&2
    exit 1
fi

# Prefer the backend venv python (the breaker itself is stdlib-only, but keeping
# one interpreter convention across FASE-0 is least-surprise). Fall back to the
# system python3 if the venv is absent.
PY="$RUNTIME_ROOT/apps/backend-rag/.venv/bin/python"
[[ -x "$PY" ]] || PY="/opt/homebrew/bin/python3"
[[ -x "$PY" ]] || PY="python3"

exec "$PY" "$BREAKER"
