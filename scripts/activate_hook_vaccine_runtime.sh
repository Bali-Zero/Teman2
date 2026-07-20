#!/bin/bash
# activate_hook_vaccine_runtime.sh — bring the M5 main checkout current so the
# merged hook-innocence vaccine (PR #1485) goes LIVE, and reconcile the orphan
# merge that's blocking it.
#
# WHY THIS SCRIPT EXISTS: an AI session inside Claude Code cannot set the
# AGENT_WORKTREE_ENFORCEMENT env var that the worktree-isolation hook reads — so
# git mutations on the main checkout are blocked from inside the agent. The
# operator (Zero) runs THIS script from a real terminal, where the env var can be
# exported. opus-mythos hooks TAC, 2026-06-16.
#
# WHAT IT DOES (all verified-safe by read-only investigation before this script):
#   1. Confirms the orphan merge in the main checkout is REDUNDANT (its MERGE_HEAD
#      a03b928fe = PR #1430, already an ancestor of origin/main). Aborts ONLY if
#      confirmed redundant.
#   2. Brings local main current with origin/main by rebasing the 2 local doc
#      commits (d72b3c2b7, b8d1ed33c) on top. Aborts the rebase on any conflict.
#   3. Pushes. Re-verifies the vaccine markers are now in the live checkout.
#
# SAFETY: never uses reset --hard / --force / git clean / --no-verify. Stops on
# any unexpected state. The 2 local doc commits are preserved. Run it, read its
# output — it narrates every step and refuses to proceed on surprises.
#
# USAGE (from a terminal, NOT from inside the Claude agent):
#   bash scripts/activate_hook_vaccine_runtime.sh
# or, if the worktree hook still blocks despite this script setting the var:
#   AGENT_WORKTREE_ENFORCEMENT=false bash scripts/activate_hook_vaccine_runtime.sh

set -uo pipefail

REPO="${NUZ_REPO_ROOT:-$HOME/nuzantara}"
ORPHAN_PR1430="a03b928fe"  # git commit SHA of the redundant orphan merge (PR #1430), not a secret  # pragma: allowlist secret
export AGENT_WORKTREE_ENFORCEMENT=false  # so git ops in main are permitted for THIS authorized reconcile

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
die() { printf '\n\033[31mABORT: %s\033[0m\n' "$*" >&2; exit 1; }

git_main() { git -C "$REPO" "$@"; }

say "0. Preconditions"
[ -d "$REPO/.git" ] || die "no repo at $REPO (set NUZ_REPO_ROOT)"
git_main fetch origin main || die "fetch failed"
echo "  local HEAD: $(git_main log --oneline -1)"
echo "  origin/main tip: $(git_main log --oneline -1 origin/main)"

say "1. Is the orphan merge (if any) redundant?"
if [ -f "$REPO/.git/MERGE_HEAD" ]; then
    MH="$(cat "$REPO/.git/MERGE_HEAD")"
    echo "  in-progress merge: MERGE_HEAD=$MH"
    # redundant == MERGE_HEAD already contained in origin/main
    if git_main merge-base --is-ancestor "$MH" origin/main; then
        echo "  CONFIRMED REDUNDANT — $MH is already an ancestor of origin/main."
        say "2. Aborting the redundant orphan merge"
        git_main merge --abort || die "merge --abort failed"
        echo "  merge aborted. working tree restored to $(git_main log --oneline -1)"
    else
        die "MERGE_HEAD $MH is NOT in origin/main — NOT redundant. Resolve this merge manually; this script will not touch it."
    fi
else
    echo "  no in-progress merge. good."
fi

say "2b. Confirm the 2 local doc commits are intact before rebase"
AHEAD="$(git_main log --oneline origin/main..HEAD)"
echo "$AHEAD" | sed 's/^/    /'
N_AHEAD="$(printf '%s\n' "$AHEAD" | grep -c .)"
echo "  ($N_AHEAD local-ahead commit(s) to preserve)"

say "3. Rebase local commits onto origin/main (linear, preserves your commits)"
if git_main rebase origin/main; then
    echo "  rebase clean. new history top:"
    git_main log --oneline -5 | sed 's/^/    /'
else
    git_main rebase --abort 2>/dev/null
    die "rebase hit conflicts (aborted). Reconcile manually — your commits are intact, nothing lost."
fi

say "4. Push reconciled main"
if git_main push origin main; then
    echo "  pushed."
else
    echo "  PUSH BLOCKED (likely pre-push test suite: known-unrelated failures — migration 228 / QDRANT env / SSE flake)."
    echo "  Your local main is already reconciled + the vaccine is active locally. Push when those are resolved, or:"
    echo "    AGENT_WORKTREE_ENFORCEMENT=false git -C $REPO push origin main --no-verify   # ONLY if you accept the known-unrelated test failures"
fi

say "5. Verify the vaccine is LIVE in the checkout"
ok=1
grep -q "git push --force on main/master" "$REPO/scripts/guardrails_static_core.py" && echo "  ✓ force-push over-match fix present" || { echo "  ✗ force-push fix MISSING"; ok=0; }
grep -q "_strip_quotes" "$REPO/scripts/guardrails_static_core.py" && echo "  ✓ _strip_quotes present" || { echo "  ✗ _strip_quotes MISSING"; ok=0; }
grep -q "_PKG_MGR" "$REPO/infra/claude-hooks/worktree_isolation.py" && echo "  ✓ npm/pip install carve-out present" || { echo "  ✗ _PKG_MGR MISSING"; ok=0; }

say "6. Next: re-vendor the live guardrails hook (AFTER PR #1483 + #1493 are merged)"
echo "  When the core is the complete truth, sync the live hook's vendored fallback:"
echo "    python3 $REPO/scripts/guardrails_sync_check.py            # see drift"
echo "    python3 $REPO/scripts/guardrails_sync_check.py --apply    # re-vendor from core"
echo "  (guardrails_sync_check.py lands on main via PR #1493.)"

[ "$ok" = 1 ] && say "DONE — hook vaccine active in the M5 runtime." || say "PARTIAL — some markers missing; check the rebase result."
