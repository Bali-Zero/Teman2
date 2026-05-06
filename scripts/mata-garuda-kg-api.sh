#!/usr/bin/env bash
# Bridge: launchd entry point for mata-garuda kg-query-api.
# TCC note: launchd-spawned /bin/zsh cannot open ~/Desktop files; we exec
# the venv python directly (adhoc-signed, bypasses TCC).
set -euo pipefail

REPO_ROOT="${MATA_GARUDA_REPO:-${HOME}/Desktop/nuzantara}"
VENV_PY="${REPO_ROOT}/apps/mata-garuda/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[$(date -u +%FT%TZ)] ERROR: venv python missing at $VENV_PY" >&2
    exit 78  # EX_CONFIG
fi

cd "${REPO_ROOT}/apps/mata-garuda"
exec "$VENV_PY" -m mata_garuda.api.kg_query
