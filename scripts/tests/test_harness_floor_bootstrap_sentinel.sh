#!/usr/bin/env bash
# Guilt + innocence corpus for harness-floor.yml's bootstrap-sentinel guard
# shape, shared verbatim by THREE call sites: Step 7c on
# scripts/ci/harness_gate_read.py, and Step 4 + Step 7b on
# scripts/ci/tracked_file_present_in_diff.sh.
#
# WHY THIS EXISTS (independent cross-family review, Kimi K3, finding #3 —
# team-lead's own words: "the one I most want fixed here... the most
# dangerous latent defect"): the original Step 7c bootstrap guard was a bare
# `[[ ! -f scripts/ci/harness_gate_read.py ]] -> exit 0`. Step 1 checks out
# the BASE ref, not the PR's own head, so a FUTURE PR that deletes this
# script would pass its own CI (base still has the file, pre-merge) and,
# once merged, every subsequent Gear-3 PR's verdict-read step would
# silently and permanently exit 0 — no verdict ever read, no red anywhere,
# forever. The sibling comment this replaced even asserted the opposite
# ("not a disarm vector... no PR can make it disappear from HEAD without
# also removing it from base after merge") — demonstrably false, and this
# is the live counterexample the reviewer supplied.
#
# EXTENDED THE SAME DAY: Step 4 and Step 7b's own bootstrap guards on
# scripts/ci/tracked_file_present_in_diff.sh had the identical shape of
# defect one level removed — instead of skipping, they INLINED a copy of
# the check on any missing script, with no bound on which PR that applied
# to. That is not "always pass" (the inline copy still validates), but it
# is still an unbounded free pass: once the shared script disappears from
# base for ANY reason, every future PR silently runs a permanently-stale
# inlined copy forever, never the shared script again — defeating the
# entire reason the check was extracted to a shared file in the first
# place (round-2 note in harness-floor.yml: a mutation to the check must be
# visible to workflow AND test from the same source). Team-lead flagged the
# collision directly: "you have just added a 4th and 5th instance of the
# pattern Kimi rates most dangerous." Fixed with the same sentinel shape as
# Step 7c, so all three call sites now share one guilt+innocence proof.
#
# THE FIX this pins, for all three call sites: the skip/inline only fires
# when the resolved PR number equals this PR's own declared bootstrap
# number (BOOTSTRAP_PR="4539" in the workflow) — the one legitimate
# one-time bootstrap window. For any OTHER PR number, a missing script
# fails closed instead of skipping or inlining.
#
# GUILT     — missing script + a PR number that is NOT the bootstrap PR ->
#             fail closed (this is the exact deletion-PR scenario).
# INNOCENCE — missing script + the bootstrap PR's own number -> skip
#             gracefully (this PR's own legitimate first CI run).
# GUILT-2   — missing script + no PR number resolvable at all (garbled
#             merge_group head_ref, e.g.) -> fail closed, never treated as
#             a free pass.
# SCAR-PIN  — the workflow declares the same bootstrap PR number and the
#             same merge_group-head_ref regex shape this test exercises, at
#             ALL THREE call sites (a count, not just a presence check —
#             catches a regression where only one or two of the three guards
#             keep the fix).
#
# Runs in any POSIX-ish bash. No network, no fixtures on disk beyond /tmp.
set -uo pipefail

FAILURES=0
fail() { echo "  ✗ $*"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW="$SCRIPT_DIR/../../.github/workflows/harness-floor.yml"

# THE CHECK UNDER TEST — verbatim shape from harness-floor.yml Step 7c's
# bootstrap-sentinel guard, parameterized so the test can control whether
# the script "exists" (SCRIPT_PRESENT=1) without touching a real file.
sentinel_verdict() {  # sentinel_verdict <script_present:0|1> <pr_number_env> <merge_group_head_ref>
  local script_present="$1" pr_number_env="$2" merge_group_head_ref="$3"
  local BOOTSTRAP_PR="4539"
  if [[ "$script_present" == "1" ]]; then
    echo "present"
    return
  fi
  local RESOLVED_PR="${pr_number_env:-}"
  if [[ -z "$RESOLVED_PR" && "$merge_group_head_ref" =~ pr-([0-9]+)- ]]; then
    RESOLVED_PR="${BASH_REMATCH[1]}"
  fi
  if [[ "$RESOLVED_PR" == "$BOOTSTRAP_PR" ]]; then
    echo "bootstrap-skip"
  else
    echo "fail-closed"
  fi
}

# --- GUILT: missing script, a DIFFERENT (future deletion) PR number ---
RESULT="$(sentinel_verdict 0 "9999" "")"
if [[ "$RESULT" == "fail-closed" ]]; then
  pass "guilt: missing script + PR #9999 (not the bootstrap PR) -> fail-closed"
else
  fail "guilt: missing script + PR #9999 -> got '$RESULT', expected fail-closed (Kimi finding #3 regression)"
fi

# --- GUILT: missing script, a future deletion PR arriving via merge_group ---
RESULT="$(sentinel_verdict 0 "" "refs/heads/gh-readonly-queue/main/pr-9999-abc123")"
if [[ "$RESULT" == "fail-closed" ]]; then
  pass "guilt: missing script + merge_group PR #9999 (not the bootstrap PR) -> fail-closed"
else
  fail "guilt: missing script + merge_group PR #9999 -> got '$RESULT', expected fail-closed"
fi

# --- INNOCENCE: missing script, THIS PR's own number (pull_request event) ---
RESULT="$(sentinel_verdict 0 "4539" "")"
if [[ "$RESULT" == "bootstrap-skip" ]]; then
  pass "innocence: missing script + PR #4539 (the declared bootstrap PR) -> bootstrap-skip"
else
  fail "innocence: missing script + PR #4539 -> got '$RESULT', expected bootstrap-skip"
fi

# --- INNOCENCE: missing script, THIS PR's own number via merge_group ---
RESULT="$(sentinel_verdict 0 "" "refs/heads/gh-readonly-queue/main/pr-4539-def456")"
if [[ "$RESULT" == "bootstrap-skip" ]]; then
  pass "innocence: missing script + merge_group PR #4539 -> bootstrap-skip"
else
  fail "innocence: missing script + merge_group PR #4539 -> got '$RESULT', expected bootstrap-skip"
fi

# --- GUILT-2: missing script, no PR number resolvable at all ---
RESULT="$(sentinel_verdict 0 "" "not-a-queue-ref")"
if [[ "$RESULT" == "fail-closed" ]]; then
  pass "guilt: missing script + unresolvable PR number -> fail-closed (never a free pass on ambiguity)"
else
  fail "guilt: missing script + unresolvable PR number -> got '$RESULT', expected fail-closed"
fi

# --- Script present: sentinel is never consulted, regardless of PR number ---
RESULT="$(sentinel_verdict 1 "9999" "")"
if [[ "$RESULT" == "present" ]]; then
  pass "innocence: script present -> sentinel bypassed entirely, normal execution"
else
  fail "innocence: script present -> got '$RESULT', expected present"
fi

# --- SCAR-PIN: the workflow declares the sentinel at ALL THREE call sites
#     (Step 4, Step 7b, Step 7c) — a count, not a bare presence check, so a
#     regression that reverts just one of the three (e.g. Step 4 or Step 7b
#     quietly going back to an unbounded inline-forever fallback) is caught
#     even though the other two would still make grep -q pass ---
if [[ -f "$WORKFLOW" ]]; then
  BOOTSTRAP_COUNT="$(grep -c 'BOOTSTRAP_PR="4539"' "$WORKFLOW")"
  if [[ "$BOOTSTRAP_COUNT" -eq 3 ]]; then
    pass "scar-pin: harness-floor.yml declares BOOTSTRAP_PR=\"4539\" at all 3 call sites"
  else
    fail "scar-pin: harness-floor.yml declares BOOTSTRAP_PR=\"4539\" $BOOTSTRAP_COUNT time(s), expected 3 (Step 4 + Step 7b + Step 7c) — a sentinel-gated guard reverted to an unbounded fallback"
  fi
  REGEX_COUNT="$(grep -cF 'pr-([0-9]+)-' "$WORKFLOW")"
  if [[ "$REGEX_COUNT" -eq 3 ]]; then
    pass "scar-pin: harness-floor.yml parses merge_group head_ref with the same regex shape at all 3 call sites"
  else
    fail "scar-pin: harness-floor.yml's merge_group PR-number regex appears $REGEX_COUNT time(s), expected 3 — has drifted from this test's copy at one or more call sites"
  fi
else
  fail "scar-pin: workflow file not found at $WORKFLOW"
fi

echo ""
if (( FAILURES > 0 )); then
  echo "FAIL: $FAILURES failure(s)"
  exit 1
fi
echo "PASS"
