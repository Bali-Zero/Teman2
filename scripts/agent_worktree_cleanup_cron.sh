#!/bin/bash
# agent_worktree_cleanup_cron.sh — periodic reaper for the agent worktree broker.
#
# W62 ANTIBODY #1: scripts/agent_start.py --cleanup is WIP-safe and skip-recent
# safe, but it is OPT-IN — nothing invoked it on a schedule, so abandoned
# worktrees accumulated for days (worktree storm, sibling-race surface growth).
# This wrapper is driven by com.nuzantara.agent-worktree-cleanup.daily.plist.
#
# Guards (all enforced inside agent_start.py --cleanup):
#   - WIP-safe   : a worktree with uncommitted changes is NEVER removed.
#   - skip-recent: a worktree touched in the last 10min (live session) is kept.
#   - kill switch: AGENT_BROKER_ENABLED=false aborts cleanly.
#
# GOTCHA (W62 audit): the broker resolves WORKTREES_DIR from the script's own
# location (parents[1]). It MUST run from the MAIN checkout, never a worktree
# copy, or it would scan .worktrees/<wt>/.worktrees/ (nonexistent) and no-op.
#
# Exit codes: 0 = clean (or live-session skips only); 1 = a WIP worktree was
# skipped (operator must commit/stash); 2 = broker disabled / env missing.

set -euo pipefail

# Hardcoded MAIN checkout — do NOT derive from $0 (this wrapper may itself be
# invoked from a worktree copy). The broker path below is the canonical one.
REPO_ROOT="${HOME}/Desktop/nuzantara"
BROKER="${REPO_ROOT}/scripts/agent_start.py"

LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/agent-worktree-cleanup.log"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"
}

# Heartbeat helper (no-op fallback if not present).
# shellcheck disable=SC1091
if ! source "${REPO_ROOT}/scripts/lib/heartbeat.sh" 2>/dev/null; then
    organism_heartbeat() { :; }
fi

if [ ! -f "$BROKER" ]; then
    log "ERROR: broker not found at $BROKER"
    organism_heartbeat "pro.agent_worktree_cleanup" "fail" "broker missing"
    exit 2
fi

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
    log "ERROR: python3 not on PATH ($PATH)"
    organism_heartbeat "pro.agent_worktree_cleanup" "fail" "python3 missing"
    exit 2
fi

log "running broker --cleanup (repo=$REPO_ROOT)"
set +e
OUTPUT="$(cd "$REPO_ROOT" && "$PYTHON" "$BROKER" --cleanup 2>&1)"
RC=$?
set -e

echo "$OUTPUT" | tee -a "$LOG"

# Heartbeat must never mask the broker's real RC under set -e (codex P3):
# guard every call with || true and exit on the captured $RC.
case "$RC" in
    0) organism_heartbeat "pro.agent_worktree_cleanup" "ok" "clean" || true ;;
    1) organism_heartbeat "pro.agent_worktree_cleanup" "warning" "WIP worktree skipped" || true ;;
    *) organism_heartbeat "pro.agent_worktree_cleanup" "fail" "exit $RC" || true ;;
esac

log "done (exit $RC)"
exit "$RC"
