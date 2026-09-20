#!/usr/bin/env bash
# test_cate_paid_budget.sh — guilt + innocence for catE-sovereignty-lint #40,
# the step that bans NEW paid per-token constructor sites against a committed
# budget.
#
# WHY THIS EXISTS. Two defects were measured on 2026-09-20, both in the same
# step, and neither could have been caught by reading it:
#
#   1. The budget is a COUNT, not a set of identities. Its file named three
#      sites; all three had been remediated and matched nothing, while the two
#      live hits were docstrings QUOTING the ban. Three phantom slots held open
#      by two quotes left room for one real new call site to land green.
#   2. Draining the budget to zero DISARMED the step. `grep -c` prints "0" and
#      exits 1 on no match, so `$(grep -c ... || echo 0)` returned the two-line
#      string "0\n0"; `[ -gt ]` then died with "integer expression expected",
#      and under `set -uo pipefail` without -e a failed test reads as FALSE.
#      The step printed OK with nine live hits.
#
# Defect 2 is the reason this file is a test and not a comment: the fix to
# defect 1 is what triggers it, so the two must be proven together.
#
# The block under test is EXTRACTED VERBATIM from the live workflow between its
# CATE40_BUDGET_BEGIN/END markers and dedented, so this test breaks the moment
# the workflow drifts from what is pinned here — same discipline as
# scripts/tests/test_pii_gate_merge_scope.sh.
#
# The guilt fixture's banned literal is ASSEMBLED at runtime rather than typed
# into this file. Not squeamishness: a spelled-out literal in prose or in a test
# source is what spent the budget in the first place, and the guard reads the
# FIXTURE, never this script — so the corpus is exactly as guilty either way.
#
# Run:  bash scripts/tests/test_cate_paid_budget.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/catE-sovereignty-lint.yml"
PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

BLOCK="$(sed -n '/CATE40_BUDGET_BEGIN/,/CATE40_BUDGET_END/p' "$WORKFLOW" | sed 's/^          //')"
if [ -z "$BLOCK" ]; then
    echo "❌ could not extract the CATE40_BUDGET block from $WORKFLOW"
    echo "   The markers are load-bearing: without them this test tests nothing."
    exit 1
fi
# Guard against the markers surviving while the logic behind them is gutted.
case "$BLOCK" in
    *BASELINE_FILE*) : ;;
    *) echo "❌ extracted block no longer reads a budget file"; exit 1 ;;
esac
case "$BLOCK" in
    *awk*) : ;;
    *) echo "❌ extracted block no longer counts the budget with awk — defect 2 is back"; exit 1 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The banned spelling, assembled so it exists only in the fixture on disk.
PAID_CALL="Anthropic(""api_key""=os.environ['X'])"
OAUTH_CALL="Anthropic(""auth_token""=os.environ['X'])"

# new_tree <name> <budget-file-body>
new_tree() {
    d="$WORK/$1"
    rm -rf "$d"
    mkdir -p "$d/.github/workflows" "$d/src"
    printf '%s\n' "$2" > "$d/.github/workflows/catE-paid-anthropic-baseline.txt"
    printf '%s\n' "$d"
}

# `bash -c`, not `sh -c`. GitHub Actions runs a `run:` block under `bash -e`,
# and the block's first line is `set -uo pipefail`. On an Ubuntu runner /bin/sh
# is dash, which has no pipefail: `dash -c "set -uo pipefail; echo X"` exits 2
# with "Illegal option -o pipefail" before reaching the scan. Measured by the
# codex-gpt-5.6-sol council seat on this PR. Under `sh` this corpus would have
# tested a shell the workflow never uses — green here, and green for the wrong
# reason on macOS, where /bin/sh is bash in POSIX mode and pipefail works.
run_step() { ( cd "$1" && bash -c "$BLOCK" 2>&1 ); }
rc_of()    { ( cd "$1" && bash -c "$BLOCK" >/dev/null 2>&1 ); echo $?; }

# expect_rc <expected-rc> <tree> <label> — `if`, not `A && B || C`: with the
# latter a passing assertion whose `ok` ever returned non-zero would silently
# also report the failure (SC2015).
expect_rc() {
    _got="$(rc_of "$2")"
    if [ "$_got" = "$1" ]; then ok "$3"; else bad "$3 (expected rc=$1, got $_got)"; fi
}

echo "catE #40 paid-constructor budget — guilt + innocence"

# ── INNOCENCE 1: empty budget, clean tree ────────────────────────────────────
T="$(new_tree innocence_clean '# only comments here')"
printf 'x = 1\n' > "$T/src/app.py"
expect_rc 0 "$T" "budget 0 + no hits: green"

# ── INNOCENCE 2: the budget reads as a single integer when it is zero ────────
#    This is the regression for defect 2 — assert the VALUE, not just the exit.
T="$(new_tree innocence_zero '# nothing but comments')"
printf 'x = 1\n' > "$T/src/app.py"
OUT="$(run_step "$T")"
case "$OUT" in
    *"baseline=0 "*) ok "empty budget reads as exactly 0 (no \"0\\n0\")" ;;
    *) bad "empty budget did not read as a bare 0 — got: $(printf '%s' "$OUT" | head -3 | tr '\n' '|')" ;;
esac

# ── GUILT 1: one new paid call site against a zero budget ────────────────────
T="$(new_tree guilt_new_site '# budget is zero')"
printf 'client = %s\n' "$PAID_CALL" > "$T/src/app.py"
expect_rc 1 "$T" "budget 0 + one paid call site: red"

# ── GUILT 2: defect 2 itself — nine hits must not pass an empty budget ───────
T="$(new_tree guilt_nine '# budget is zero')"
i=1
while [ "$i" -le 9 ]; do
    printf 'client = %s\n' "$PAID_CALL" > "$T/src/mod$i.py"
    i=$((i + 1))
done
expect_rc 1 "$T" "nine hits against an empty budget: red (defect 2 stays fixed)"

# ── INNOCENCE 3: the sanctioned OAuth constructor must not trip ──────────────
T="$(new_tree innocence_oauth '# budget is zero')"
printf 'client = %s\n' "$OAUTH_CALL" > "$T/src/app.py"
expect_rc 0 "$T" "OAuth bearer constructor: green"

# ── INNOCENCE 4: a guilt corpus under tests/ or test_ stays legal ────────────
T="$(new_tree innocence_corpus '# budget is zero')"
mkdir -p "$T/src/tests"
printf 'client = %s\n' "$PAID_CALL" > "$T/src/tests/fixture.py"
printf 'client = %s\n' "$PAID_CALL" > "$T/src/test_fixture.py"
expect_rc 0 "$T" "tests/ and test_ fixtures: green (a guard needs its guilt corpus)"

# ── GUILT 3: a missing budget file fails closed ──────────────────────────────
T="$(new_tree guilt_missing '# placeholder')"
rm -f "$T/.github/workflows/catE-paid-anthropic-baseline.txt"
printf 'x = 1\n' > "$T/src/app.py"
expect_rc 1 "$T" "missing budget file: red (fails closed)"

# ── GUILT 4: a non-numeric budget fails closed ───────────────────────────────
T="$(new_tree guilt_garbage 'not-a-number')"
printf 'x = 1\n' > "$T/src/app.py"
OUT="$(run_step "$T")"
RC="$(rc_of "$T")"
# One non-comment line IS a budget of 1, so this tree is legitimately green;
# what must hold is that the count itself never leaves awk as a non-integer.
case "$OUT" in
    *"baseline=1 "*) ok "a budget line of arbitrary text still counts as 1, not as its content" ;;
    *) bad "budget line miscounted — got: $(printf '%s' "$OUT" | head -3 | tr '\n' '|')" ;;
esac
if [ "$RC" != "0" ]; then bad "a budget of 1 with no hits should be green (rc=$RC)"; fi

# ── RATCHET: the budget on disk must stay at zero ───────────────────────────
# Raised by the gate session on PR #6943: at budget 0 the file is an empty
# contract, and a "temporary" line added later makes the guard tolerant again
# in silence — nothing else in CI would say a word. This case is the noise.
# It is NOT a claim that the budget may never rise: if you are adding a line
# you are asking for a paid call site to be tolerated on main, and updating
# this number is the deliberate act that says so out loud, in a diff, with a
# reason in the PR body.
LIVE_BUDGET=$(awk '!/^[[:space:]]*(#|$)/ {n++} END {print n+0}'     "$REPO_ROOT/.github/workflows/catE-paid-anthropic-baseline.txt")
if [ "$LIVE_BUDGET" = "0" ]; then
    ok "the committed budget is still 0"
else
    bad "the committed budget is now $LIVE_BUDGET, not 0 — if that is deliberate, say why in the PR body and update this case"
fi

echo
echo "  passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
