#!/bin/bash
# wr2-worktree-gc-run.sh — W84 trampoline wrapper for com.balizero.wr2.worktree-gc.daily.
#
# Promotes infra/launchagents/com.balizero.wr2.worktree-gc.daily.plist.example
# to real installable canon (A1 finding #4, 2026-07-14: the cron was NEVER
# installed — only the .example template existed on disk). Follows the W84
# trampoline sweep pattern (#2421, 2026-07-13): the payload it invokes
# (scripts/wr2_worktree_gc.py) touches the repo checkout under
# ~/nuzantara, so this wrapper probes/re-execs BEFORE any Desktop
# access, same as matagaruda-consumer-lag-run.sh / curiosity-batch.sh.
#
# REPORT-ONLY BY DESIGN (see PR body for the two blocking findings this
# uncovered): scripts/wr2_worktree_gc.py does NOT implement the 3-AND policy
# (W80/W88 — no live-process check, no lease check, no content-on-main check,
# purely age>24h) AND its WORKTREE_PREFIX ("wr2-run-") no longer matches any
# worktree scripts/agent_start.py actually creates (current convention is
# "<lane>-<task_id>", e.g. "wr2-b13-worktree-gc" — verified live on Pro: a
# 31-day-old orphan `.worktrees/wr2-pipeline-consolidation` would NOT be
# caught even with --apply). Until a follow-up closes both gaps, this
# wrapper deliberately never passes --apply — it is safe to arm on a
# schedule (dry-run report every run), but arming --apply is a decision for
# whoever fixes wr2_worktree_gc.py, not for this promotion PR.
#
# Deployed copy: ~/scripts/wr2-worktree-gc-run.sh (outside TCC-protected
# ~/Desktop — scar W84). Declared pair: infra/home-fork/declared-pairs.json.

set -uo pipefail   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.wr2_worktree_gc"
LOG="$HOME/logs/wr2-worktree-gc.log"
mkdir -p "$HOME/logs"
SIDECAR_DIR="$HOME/.organism/last_seen"

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${WR2_WORKTREE_GC_ENABLED:-true}" = "false" ]; then
    echo "[$(date)] kill switch WR2_WORKTREE_GC_ENABLED=false — exiting" >> "$LOG"
    heartbeat "disabled" "kill switch"
    exit 0
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG"
fi

REPO="${REPO_ROOT:-$HOME/nuzantara}"
PYBIN="$REPO/apps/backend-rag/.venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="python3"

cd "$REPO" || {
    echo "[$(date)] FATAL: cannot cd to REPO=$REPO" >> "$LOG"
    heartbeat "error" "cannot cd to REPO=$REPO"
    exit 1
}

"$PYBIN" "$REPO/scripts/wr2_worktree_gc.py" --log-level INFO >> "$LOG" 2>&1
RC=$?

echo "[wr2-worktree-gc] exit=$RC" >> "$LOG"
if [ "$RC" -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"
fi
exit "$RC"
