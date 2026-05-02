#!/usr/bin/env bash
# Launcher for com.nuzantara.heartbeat-bridge LaunchAgent (Sprint 1.B Task 5 partial).
#
# Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
# Cicatrix: 2026-05-02 test-mock-vs-prod (new 3-PR chain that this resolves).
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
CELL_DIR="$REPO_ROOT/apps/cell"
CELL_CORE_DIR="$REPO_ROOT/packages/cell-core"

cd "$CELL_DIR"
export PYTHONPATH=".:$CELL_CORE_DIR:${PYTHONPATH:-}"

# Use Cell's own .venv python (3.11) so we share dependencies (httpx,
# pydantic, etc.) with the main Cell daemon. macOS launchctl resolves
# `python3` to Xcode 3.9 even with /opt/homebrew/bin in PATH env var,
# and 3.9 has an asyncio cross-loop bug that breaks the polling loop.
# Brew python3.12 fixes the asyncio bug but lacks httpx; .venv has both.
PYTHON_BIN="${HEARTBEAT_PYTHON:-$CELL_DIR/.venv/bin/python3}"
exec "$PYTHON_BIN" scripts/heartbeat_bridge_loop.py
