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
# Exit codes (Antibody Debt ledger #2, 2026-06-13): 0 = clean OR expected
# skips (live-session / WIP — the broker is doing its job, not failing);
# 2 = broker disabled / env missing; other = real broker error.
# RATIONALE: the broker's RC=1 on WIP-skip is BY DESIGN (W62 WIP-safe guard),
# but propagating it from an unattended nightly cron made launchd count a
# permanent "failure" every night (observed 2026-06-12: 3 WIP skips → exit 1
# → failed-jobs noise, DLQ-classification surface). The operator signal is
# preserved through the heartbeat status=warn AND the WARN lines in the log —
# a non-zero exit adds no information there, only noise.

set -euo pipefail

# Hardcoded MAIN checkout — do NOT derive from $0 (this wrapper may itself be
# invoked from a worktree copy). The broker path below is the canonical one.
# Env override exists for the test harness ONLY (point at a stub repo).
REPO_ROOT="${AGENT_WORKTREE_CLEANUP_REPO_ROOT:-${HOME}/nuzantara}"
BROKER="${REPO_ROOT}/scripts/agent_start.py"

LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/agent-worktree-cleanup.log"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"
}

# Heartbeat helper (no-op fallback if not present).
# LATENT-BUG fix (found by the stub harness, 2026-06-13): bash 3.2 EXITS the
# whole non-interactive script when `source` cannot find the file — even
# inside `if !` under set -e. Guard with an existence check instead.
if [ -f "${REPO_ROOT}/scripts/lib/heartbeat.sh" ]; then
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/scripts/lib/heartbeat.sh" || true
fi
if ! declare -F organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat() { :; }
fi

# Machine-aware organ id (TAC-2 A2, 2026-07-05): this cron runs on all three
# machines but hardcoded "pro." — an M5/Mini run forged a Pro-resident heartbeat
# (boundary repo<->machine; proprioception flagged the wrong-prefix sidecar).
# Env override exists for the test harness ONLY.
case "$(hostname -s | tr '[:upper:]' '[:lower:]')" in
    nuzantara)  _ORGAN_MACHINE="pro" ;;
    mini-pro2)  _ORGAN_MACHINE="mini" ;;
    air-m5)     _ORGAN_MACHINE="m5" ;;
    *)          _ORGAN_MACHINE="$(hostname -s | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '_')" ;;
esac
ORGAN_ID="${AGENT_WORKTREE_CLEANUP_ORGAN_ID:-${_ORGAN_MACHINE}.agent_worktree_cleanup}"

if [ ! -f "$BROKER" ]; then
    log "ERROR: broker not found at $BROKER"
    organism_heartbeat "$ORGAN_ID" "fail" "broker missing"
    exit 2
fi

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
    log "ERROR: python3 not on PATH ($PATH)"
    organism_heartbeat "$ORGAN_ID" "fail" "python3 missing"
    exit 2
fi

log "running broker --cleanup (repo=$REPO_ROOT)"
set +e
OUTPUT="$(cd "$REPO_ROOT" && "$PYTHON" "$BROKER" --cleanup 2>&1)"
RC=$?
set -e

echo "$OUTPUT" | tee -a "$LOG"

# Heartbeat must never mask the broker's real RC under set -e (codex P3):
# guard every call with || true.
# RC=1 (WIP skipped) maps to exit 0: expected guard behavior in cron context,
# signal carried by heartbeat=warn + WARN log lines (ledger #2, 2026-06-13).
case "$RC" in
    0)
        organism_heartbeat "$ORGAN_ID" "ok" "clean" || true
        EXIT_RC=0
        ;;
    1)
        WIP_COUNT="$(printf '%s\n' "$OUTPUT" | grep -c 'WARN: skip' || true)"
        organism_heartbeat "$ORGAN_ID" "warn" \
            "WIP worktree skipped (${WIP_COUNT}x) — commit/stash to let the reaper through" || true
        log "WARN: ${WIP_COUNT} WIP worktree(s) skipped — expected guard, not a failure"
        EXIT_RC=0
        ;;
    *)
        organism_heartbeat "$ORGAN_ID" "fail" "exit $RC" || true
        EXIT_RC="$RC"
        ;;
esac

log "done (broker rc=$RC, exit $EXIT_RC)"
exit "$EXIT_RC"
