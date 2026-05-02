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

# Use brew python 3.12 explicitly. macOS LaunchAgents resolve `python3` to
# Xcode's 3.9 even with /opt/homebrew/bin in PATH — the env var just
# isn't enough for command lookup at exec time. Discovered 2026-05-02:
# 3.9 raises "got Future attached to a different loop" on asyncio.Event
# inside asyncio.wait_for, breaking the polling loop.
PYTHON_BIN="${HEARTBEAT_PYTHON:-/opt/homebrew/bin/python3.12}"
exec "$PYTHON_BIN" scripts/heartbeat_bridge_loop.py
