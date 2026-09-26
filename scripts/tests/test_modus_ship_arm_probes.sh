#!/usr/bin/env bash
# test_modus_ship_arm_probes.sh — pins the two SHIP+ARM arming probes documented
# in `.claude/skills/modus/SKILL.md` (PENDING-ARMS L191/L193, opened 2026-07-30):
#
#   1. A `gh run rerun` replays the STALE `refs/pull/N/merge` ref, not the PR
#      against current main — the honest probe is `git show refs/pull/N/merge:<file>`
#      (content), not the gesture of re-running.
#   2. "Is this PR armed" needs both `autoMergeRequest` and `isInMergeQueue` —
#      either alone reports one of the two valid armed states as UNARMED.
#
# Both were measured live and never made it into the loop's own doctrine, so a
# session kept re-deriving them from a half-signal. This test fails on the
# pre-fix SKILL.md (neither probe documented) and passes once both are.
#
# Run:  bash scripts/tests/test_modus_ship_arm_probes.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL="$REPO_ROOT/.claude/skills/modus/SKILL.md"
PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

if [ ! -f "$SKILL" ]; then
    echo "❌ $SKILL not found"
    exit 1
fi

if grep -q 'git show refs/pull/N/merge:<file>' "$SKILL"; then
    ok "L191: the content-probe for a re-run (git show refs/pull/N/merge:<file>) is documented"
else
    bad "L191: no mention of the git-show content-probe for a stale merge ref"
fi

if grep -q 'gh run rerun' "$SKILL" && grep -q 'STALE' "$SKILL"; then
    ok "L191: the stale-merge-ref hazard itself is named"
else
    bad "L191: 'gh run rerun' replaying a STALE ref is not named"
fi

if grep -q 'autoMergeRequest != null OR isInMergeQueue' "$SKILL"; then
    ok "L193: the two-field armed-state predicate is documented"
else
    bad "L193: no two-field predicate for merge-queue armed state"
fi

echo "────────────────────────────────────────────────────────────────────────"
echo "  passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
