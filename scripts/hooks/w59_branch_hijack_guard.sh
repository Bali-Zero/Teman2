#!/bin/bash
# W59 branch-hijack guard — opt-in pre-commit assertion.
#
# Reference: .claude/rules/cicatrix-scars.md ### W59 (2026-05-27).
# Symptom: with N parallel Claude/Codex sessions on the same worktree, a
# sibling `git checkout -b ...` between your `git add` and `git commit` can
# silently retarget your commit to THEIR branch. `git push origin <BRANCH>`
# then says "Everything up-to-date" while your work sits on a different ref
# (or becomes orphan).
#
# This script is the body of `.git/hooks/pre-commit` for that check.
# It is opt-in via env var OR sentinel file — no-op otherwise.
#
# Wiring: append to `.git/hooks/pre-commit` (see scripts/hooks/install.sh)
# or call directly from your custom hook.
#
# Modes:
#   1. Env var:        BRANCH_EXPECTED=feat/foo git commit -m "..."
#   2. Sentinel file:  echo "feat/foo" > .git/EXPECTED_BRANCH; git commit ...
#   3. Skip:           BRANCH_EXPECTED_SKIP=1 git commit ...

set -u

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")

if [ -n "${BRANCH_EXPECTED_SKIP:-}" ]; then
    exit 0
fi

EXPECTED="${BRANCH_EXPECTED:-}"
if [ -z "$EXPECTED" ] && [ -f ".git/EXPECTED_BRANCH" ]; then
    EXPECTED=$(tr -d '[:space:]' < .git/EXPECTED_BRANCH)
fi

if [ -z "$EXPECTED" ]; then
    # No expectation set → no-op (preserves all existing flows)
    exit 0
fi

if [ "$BRANCH" != "$EXPECTED" ]; then
    cat >&2 <<EOF
❌ W59 branch-hijack guard: HEAD on '$BRANCH' but expected '$EXPECTED'
   A sibling session may have checked out a different branch on this worktree.
   Verify with: git symbolic-ref --short HEAD
   Override:    BRANCH_EXPECTED_SKIP=1 git commit ...
   Or:          rm .git/EXPECTED_BRANCH if no longer relevant.
EOF
    exit 1
fi

exit 0
