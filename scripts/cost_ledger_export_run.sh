#!/usr/bin/env bash
# cost_ledger_export_run.sh — LaunchAgent wrapper for the cost-ledger exporter.
#
# Runs cost_ledger_export.py with the backend venv python (which carries
# asyncpg — the system python3 does NOT). NO secrets in this wrapper or the
# plist: the exporter reads the read-only PG password from the macOS Keychain
# (service nuzantara-postgres-readonly) itself, or from COST_LEDGER_DSN if the
# operator sets it. READ-ONLY against Fly PG.
#
# RUNTIME HOME = the deploy worktree (~/nuzantara-deploy).
# Kill-switch: COST_LEDGER_EXPORT_OFF=1

set -uo pipefail

if [[ "${COST_LEDGER_EXPORT_OFF:-0}" == "1" ]]; then
    echo "cost_ledger_export_run: disabled via COST_LEDGER_EXPORT_OFF=1" >&2
    exit 0
fi

RUNTIME_ROOT="${COST_LEDGER_RUNTIME_ROOT:-$HOME/nuzantara-deploy}"
EXPORTER="$RUNTIME_ROOT/scripts/cost_ledger_export.py"

if [[ ! -f "$EXPORTER" ]]; then
    echo "cost_ledger_export_run: FATAL — exporter not found at $EXPORTER" >&2
    exit 1
fi

# asyncpg lives in the backend venv; the system python3 lacks it.
PY="$RUNTIME_ROOT/apps/backend-rag/.venv/bin/python"
[[ -x "$PY" ]] || PY="/opt/homebrew/bin/python3"
[[ -x "$PY" ]] || PY="python3"

exec "$PY" "$EXPORTER"
