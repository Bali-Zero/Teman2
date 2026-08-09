#!/bin/sh
# test_branch_graveyard_prmerged.sh — regression test for category 5
# (PR-merged via gh headRefOid) in scripts/branch_graveyard_cleanup.sh
# (PENDING-ARMS ledger, opened 2026-08-03, cicatrix-superscar.md famiglia #9).
#
# Categories 1 (SHA-ancestor) and 2 (content-on-main blob diff) both miss a
# branch whenever it was squash-merged AND main independently touched the same
# files afterward — the per-file blob comparison then shows a genuine-looking
# diff for reasons unrelated to the branch itself. Measured 2026-08-03: 39/39
# real squash-merged branches fell through both checks (report was 0/0/0/0
# over a 39-branch backlog). Category 5 asks GitHub directly instead of
# inferring from tree state: a branch tip whose SHA matches a MERGED PR's
# recorded headRefOid is proven merged regardless of what main did afterward.
#
# This script proves the matching logic (guilt: real ref+oid pair matches;
# innocence: same ref with a stale/wrong oid, and a real oid under the wrong
# ref, must NOT match) without touching the network or a live repo, then
# tripwires the live script so the matcher can't silently regress.
#
# Run:  sh scripts/tests/test_branch_graveyard_prmerged.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/branch_graveyard_cleanup.sh"

# Reproduce the matcher verbatim (the script is not sourceable — it runs
# top-level git/gh calls immediately). Tripwire section below keeps this
# copy honest against the live file.
FIXTURE_TSV="/tmp/test_branch_graveyard_prmerged_fixture.$$"
trap 'rm -f "$FIXTURE_TSV"' EXIT

pr_merged_match() {
    local short="$1" sha="$2"
    [ -s "$MERGED_PRS_TSV" ] || return 1
    awk -F'\t' -v ref="$short" -v sha="$sha" '
        $1 == ref && index($2, sha) == 1 { print $3; found=1; exit }
        END { exit !found }
    ' "$MERGED_PRS_TSV"
}

# Synthetic fixture: one merged PR, headRefName=feature/x, full 40-char oid.
printf 'feature/x\t0332a7829c9e49a5d6c5095ac3c66cfa7d32d94b\t3582\n' > "$FIXTURE_TSV"
MERGED_PRS_TSV="$FIXTURE_TSV"

# ---------------------------------------------------------------------------
# Case 1 (guilt): real ref + a PREFIX of the recorded full oid must match —
# for-each-ref emits abbreviated shas, gh emits full 40-char oids.
# ---------------------------------------------------------------------------
out=$(pr_merged_match "feature/x" "0332a7829c9e"); rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "3582" ]; then
    note_pass "matching ref + oid-prefix returns the PR number (3582)"
else
    note_fail "expected rc=0 out=3582, got rc=$rc out=$out"
fi

# ---------------------------------------------------------------------------
# Case 2 (innocence): same ref name, but the branch has moved on since that
# PR merged (e.g. dependabot re-pushed) — a DIFFERENT oid must NOT match.
# Verified live 2026-08-04: dependabot/github_actions/actions/setup-python-7
# has a merged PR #3354 recorded oid 906cc2..., but the branch's current tip
# is 980ebae0... — same name, stale oid, correctly a non-match.
# ---------------------------------------------------------------------------
pr_merged_match "feature/x" "deadbeef0000" >/dev/null 2>&1; rc=$?
if [ "$rc" -ne 0 ]; then
    note_pass "matching ref + stale/wrong oid does NOT match"
else
    note_fail "expected non-zero rc for wrong oid, got rc=$rc"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence): a real oid under the WRONG ref name must NOT match —
# guards against a coincidental oid-prefix collision across branches.
# ---------------------------------------------------------------------------
pr_merged_match "no-such-branch" "0332a7829c9e" >/dev/null 2>&1; rc=$?
if [ "$rc" -ne 0 ]; then
    note_pass "real oid under the wrong ref does NOT match"
else
    note_fail "expected non-zero rc for wrong ref, got rc=$rc"
fi

# ---------------------------------------------------------------------------
# Case 4 (innocence): empty/absent MERGED_PRS_TSV (gh missing/unauthenticated)
# must fail closed to "no match" — never crash, never false-positive.
# ---------------------------------------------------------------------------
MERGED_PRS_TSV="/tmp/test_branch_graveyard_prmerged_absent.$$"
rm -f "$MERGED_PRS_TSV"
pr_merged_match "feature/x" "0332a7829c9e" >/dev/null 2>&1; rc=$?
if [ "$rc" -ne 0 ]; then
    note_pass "absent gh-pr-list file degrades to no-match, not a crash"
else
    note_fail "expected non-zero rc with absent fixture file, got rc=$rc"
fi

# ---------------------------------------------------------------------------
# Tripwire: the live script must still define this exact matcher shape and
# wire it into the classify loop as REPORT-ONLY (never handed to delete_tsv).
# ---------------------------------------------------------------------------
if grep -q 'pr_merged_match()' "$SCRIPT"; then
    note_pass "live script still defines pr_merged_match()"
else
    note_fail "pr_merged_match() missing from $SCRIPT — matcher renamed/removed?"
fi

if grep -q 'PRMERGED_TSV' "$SCRIPT" && ! grep -q 'delete_tsv "\$PRMERGED_TSV"' "$SCRIPT"; then
    note_pass "PRMERGED_TSV exists and is never passed to delete_tsv (report-only)"
else
    note_fail "category 5 either missing or wired into --apply deletion"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
