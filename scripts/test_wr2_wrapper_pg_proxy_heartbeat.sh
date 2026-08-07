#!/usr/bin/env bash
# Developer entrypoint for the Runtime Truth WR2 wrapper contract.
#
# CI does not execute this shell process and accepts no evidence from it. The
# Python parent owns all four fake worlds, invokes the real production wrapper
# directly, and observes only wrapper exit codes plus heartbeat sidecars. This
# file is intentionally only a convenient local delegator to that parent suite.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${RUNTIME_TRUTH_PYTHON:-$REPO_ROOT/apps/backend-rag/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    printf 'Runtime Truth Python missing or not executable: %s\n' "$PYTHON_BIN" >&2
    exit 69
fi

exec "$PYTHON_BIN" "$REPO_ROOT/scripts/runtime_truth_ci_gauntlet.py" "$@"
