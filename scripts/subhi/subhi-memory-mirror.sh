#!/usr/bin/env bash
# subhi-memory-mirror.sh — thin bash wrapper that delegates to
# subhi-memory-mirror.py. The Python implementation is canonical;
# this wrapper exists so LaunchAgent (and existing bash callers)
# can invoke a stable .sh entry point.
#
# Per addendum B (option B): this script writes a filtered mirror of
# Antonello's ~/.claude memory dir to a local staging directory. It
# does NOT push to git. Distribution to Subhi happens via rsync over
# Tailscale in a separate task (T3).
#
# Env:
#   CONFIG_OVERRIDE_SOURCE_DIR — used by tests
#   CONFIG_OVERRIDE_DEST_DIR   — used by tests
#   DRY_RUN                    — informational only (no git step exists)
#
# Args:
#   --config PATH              — YAML config path (default: alongside this script)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/subhi-memory-mirror.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
  echo "ERROR: ${PY_SCRIPT} not found" >&2
  exit 1
fi

# Pick a Python interpreter.
if command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "ERROR: python3 not found in PATH" >&2
  exit 1
fi

exec "$PYTHON" "$PY_SCRIPT" "$@"
