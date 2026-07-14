#!/bin/bash
# wr2-worktree-gc-run.sh — W84 trampoline wrapper for com.balizero.wr2.worktree-gc.daily.
#
# Promotes infra/launchagents/com.balizero.wr2.worktree-gc.daily.plist.example
# to real installable canon (A1 finding #4, 2026-07-14: the cron was NEVER
# installed — only the .example template existed on disk). Follows the W84
# trampoline sweep pattern (#2421, 2026-07-13): the payload it invokes
# (scripts/wr2_worktree_gc.py) touches the repo checkout under
# ~/Desktop/nuzantara, so this wrapper probes/re-execs BEFORE any Desktop
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

set -uo pipefail

LOG="$HOME/logs/wr2-worktree-gc.log"
mkdir -p "$HOME/logs"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG"
fi

REPO="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
PYBIN="$REPO/apps/backend-rag/.venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="python3"

cd "$REPO" || {
    echo "[$(date)] FATAL: cannot cd to REPO=$REPO" >> "$LOG"
    exit 1
}

"$PYBIN" "$REPO/scripts/wr2_worktree_gc.py" --log-level INFO >> "$LOG" 2>&1
RC=$?

echo "[wr2-worktree-gc] exit=$RC" >> "$LOG"
exit "$RC"
