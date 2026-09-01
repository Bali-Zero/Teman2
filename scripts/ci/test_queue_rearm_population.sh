#!/usr/bin/env bash
# Guilt + innocence corpus for scripts/ci/queue_rearm_population.sh
#
# GUILT    — a pull request whose mergeability GitHub has not finished computing
#            must be COUNTED as undecidable, never dropped into the clean bucket.
# INNOCENCE— a world with no undecided state must still read as decidable, so the
#            new guard cannot turn a healthy run into a permanent "no verdict".
#
# The corpus drives the REAL file (not a copy of its jq expressions), which is
# the whole reason that logic was split out of `queue_rearm.sh`.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNDER_TEST="$SCRIPT_DIR/queue_rearm_population.sh"
[[ -x "$UNDER_TEST" ]] || { echo "FATAL: $UNDER_TEST missing or not executable"; exit 1; }

pass=0
fail=0

# check <name> <mode> <json> <expected-stdout> <expected-rc>
check() {
  local name="$1" mode="$2" json="$3" want_out="$4" want_rc="$5"
  local got_out got_rc
  got_out=$(printf '%s' "$json" | "$UNDER_TEST" "$mode" 2>/dev/null); got_rc=$?
  if [[ "$got_out" == "$want_out" && "$got_rc" == "$want_rc" ]]; then
    printf '  ✅ %s\n' "$name"
    pass=$((pass + 1))
  else
    printf '  ❌ %s\n     want out=%q rc=%s\n     got  out=%q rc=%s\n' \
      "$name" "$want_out" "$want_rc" "$got_out" "$got_rc"
    fail=$((fail + 1))
  fi
}

ARMED='{"number":1,"mergeable":"MERGEABLE","autoMergeRequest":{"enabledAt":"x"},"title":"armed"}'
ORPHAN='{"number":2,"mergeable":"MERGEABLE","autoMergeRequest":null,"title":"orphan"}'
CONFLICT='{"number":3,"mergeable":"CONFLICTING","autoMergeRequest":null,"title":"conflicting"}'
UNKNOWN='{"number":4,"mergeable":"UNKNOWN","autoMergeRequest":null,"title":"recomputing"}'
ALIEN='{"number":5,"mergeable":"SOMETHING_NEW","autoMergeRequest":null,"title":"future value"}'

echo "=== GUILT: an undecided state must be counted, never silently dropped ==="

# The exact shape measured on 2026-07-28 seconds after a merge to main: real
# orphans, all of them mid-recomputation. The old code saw zero candidates here
# and printed "✅ no orphaned pull request".
check "3 unarmed PRs all UNKNOWN -> 0 candidates" \
  --candidates "[$UNKNOWN,$UNKNOWN,$UNKNOWN]" "" 0
check "3 unarmed PRs all UNKNOWN -> 3 undecidable" \
  --undecidable "[$UNKNOWN,$UNKNOWN,$UNKNOWN]" "3" 0

# Mixed: the candidate list is real but INCOMPLETE. Silence here would be a
# partial answer presented as a total one.
check "1 orphan + 2 UNKNOWN -> still 2 undecidable" \
  --undecidable "[$ORPHAN,$UNKNOWN,$UNKNOWN]" "2" 0

# A value this script has never heard of must land in the bucket that forces a
# re-run, not in the clean one.
check "an unrecognised mergeable value counts as undecidable" \
  --undecidable "[$ALIEN]" "1" 0

echo
echo "=== INNOCENCE: a decided world must not be dragged into 'no verdict' ==="

check "armed + conflicting only -> 0 undecidable" \
  --undecidable "[$ARMED,$CONFLICT]" "0" 0
check "armed + conflicting only -> 0 candidates" \
  --candidates "[$ARMED,$CONFLICT]" "" 0
check "a real orphan is still found" \
  --candidates "[$ORPHAN,$ARMED]" "$(printf '2\torphan')" 0
check "a real orphan is not called undecidable" \
  --undecidable "[$ORPHAN,$ARMED]" "0" 0
# An ARMED pull request mid-recomputation is not orphaned — it is armed. Only
# the unarmed ones can be orphans, so this must not inflate the count.
check "an ARMED PR that is UNKNOWN is not undecidable-orphaned" \
  --undecidable '[{"number":6,"mergeable":"UNKNOWN","autoMergeRequest":{"enabledAt":"x"},"title":"armed+unknown"}]' "0" 0

echo
echo "=== GUILT: a live mergeQueueEntry means armed, whatever mergeable/autoMergeRequest say ==="
echo "    (the #5422 shape — scripts/lint_arm_probe.py; autoMergeRequest reads null both"
echo "    when never armed AND when the queue just consumed the request on entry)"

# The exact shape measured live on PR #5422: arming had SUCCEEDED
# (`mergeQueueEntry {position: 1, state: AWAITING_CHECKS}`) while
# `autoMergeRequest` simultaneously read null and `mergeable` read MERGEABLE.
# The selectors before this fix (mergeable + autoMergeRequest alone) called
# this an "unarmed candidate" — a correctly-armed PR reported as needing
# re-arming. This is the RED case: it fails against the pre-fix selector and
# must pass here.
QUEUED='{"number":7,"mergeable":"MERGEABLE","autoMergeRequest":null,"mergeQueueEntry":{"state":"AWAITING_CHECKS","position":1},"title":"queued-null-automerge"}'
# Same disease, met from the --undecidable side: a queue entry proves armed
# even while `mergeable` is still UNKNOWN mid-recomputation — it must not be
# double-counted as an undecided orphan on top of being wrongly excluded from
# --candidates.
QUEUED_UNKNOWN='{"number":8,"mergeable":"UNKNOWN","autoMergeRequest":null,"mergeQueueEntry":{"state":"QUEUED","position":2},"title":"queued-recomputing"}'

check "a PR with a live mergeQueueEntry is never a candidate, even with autoMergeRequest:null + mergeable:MERGEABLE" \
  --candidates "[$QUEUED]" "" 0
check "a PR with a live mergeQueueEntry is never undecidable-orphaned, even with mergeable:UNKNOWN" \
  --undecidable "[$QUEUED_UNKNOWN]" "0" 0
# INNOCENCE half of the same fix: excluding the queued PR must not swallow a
# real orphan sitting right beside it in the same population.
check "a queued PR does not hide a real orphan sitting beside it" \
  --candidates "[$QUEUED,$ORPHAN]" "$(printf '2\torphan')" 0
check "a queued PR (UNKNOWN) does not inflate undecidable when a real UNKNOWN orphan is also present" \
  --undecidable "[$QUEUED_UNKNOWN,$UNKNOWN]" "1" 0

echo
echo "=== FAIL-CLOSED: an unreadable set is never an empty one ==="

check "non-array input -> rc 3" --undecidable '{"not":"an array"}' "" 3
check "empty string input -> rc 3" --undecidable '' "" 3
check "null input -> rc 3" --undecidable 'null' "" 3
check "unknown mode -> rc 3" --nope "[$ORPHAN]" "" 3

echo
echo "─── $pass passed · $fail failed"
(( fail == 0 )) || exit 1
