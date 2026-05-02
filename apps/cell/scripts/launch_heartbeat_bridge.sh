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

# Use system python3 (3.11+); the loop has no heavy deps beyond httpx
# (already a Cell dep) + cell.sensors.channel_sensor.
exec python3 scripts/heartbeat_bridge_loop.py
