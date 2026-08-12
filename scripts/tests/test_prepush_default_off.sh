#!/bin/sh
# test_prepush_default_off.sh — guilt+innocence for the 2026-08-13 flip of
# `.husky/pre-push`'s PREPUSH_RUN_BACKEND seed default (1 -> 0).
#
# WHY (measured on M5, /tmp/*push*.log, 88 real pushes over ~2.7 days): the
# backend suite used to run LOCALLY by default whenever the path-aware
# classifier's verdict was "full". Of 88 pushes, only 2 (2.3%) were genuine
# test failures; 26 (30%) — 9 lock-timeout + 17 SIGTERM-killed — produced NO
# verdict at all, purely from single-flight lock contention (4500s timeout,
# ~1h50m/lane under contention — arithmetic failure from the third
# concurrent lane on). CI's `Backend Tests (Python)` required check is a
# verified strict superset of what this hook runs locally, so the local run
# added cost with zero unique safety benefit. See the DEFAULT-OFF comment
# block in .husky/pre-push (right above `PREPUSH_RUN_BACKEND=0`) for the
# full writeup.
#
# This file proves FOUR things, per the ship contract for this change:
#   1. GUILT: with the new default and no override, a classifier verdict of
#      "full" (i.e. the diff DOES touch backend-relevant paths) still does
#      NOT run the suite locally.
#   2. INNOCENCE 1: PREPUSH_FULL=1 still forces PREPUSH_RUN_BACKEND=1 (the
#      escape hatch this whole change depends on staying alive).
#   3. INNOCENCE 2 (structural, delegated): the honest-verdict fail-closed
#      guard at the bottom of the hook (`if [ "$PREPUSH_RUN_BACKEND" = "1"
#      ] && [ "${BACKEND_SUITE_RAN:-0}" != "1" ]`) is EXERCISED, unchanged,
#      by scripts/tests/test_prepush_honest_verdict.py — this file does not
#      re-derive that proof, it tripwires that the guard's condition text is
#      still byte-identical to what this diff shipped it as, so a future
#      edit to THAT guard cannot silently drift without also touching the
#      file the honest-verdict corpus already watches.
#   4. INNOCENCE 3: the fast, non-suite checks (the trusted-helper-bundle
#      guard at the very top of the file) still run and can still block a
#      push regardless of PREPUSH_RUN_BACKEND — proven against the REAL
#      hook file, not a mirror, so it also verifies nothing above the
#      path-aware block regressed.
#
# Case 2 (the behavioural guilt case) extracts the REAL path-aware block —
# `if [ "${PREPUSH_FULL:-0}" = "1" ]; then` through its own matching `fi` —
# verbatim from the live hook and executes it under `sh -e`, with
# PREPUSH_CLASSIFIER pointed at a stub that always answers "full" (a real
# backend-touching diff). Extraction, not re-typing: this is the same
# technique scripts/tests/test_prepush_honest_verdict.py uses for the
# suite-execution region, applied to the classifier-gating region instead —
# it breaks the moment the live logic drifts from what this test assumes,
# rather than silently testing a stale copy (cicatrix-superscar.md #6,
# "anti-hallucination blindness" lineage: never build on a re-typed mirror
# of code you could have executed).
#
# `scripts/prepush_classify.py` itself is untouched by this diff and is
# proven separately by scripts/tests/test_prepush_classify.py — this file
# stubs it out on purpose, it does not re-test it.
#
# Run:  sh scripts/tests/test_prepush_default_off.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0
note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
HOOK_FILE="$REPO_ROOT/.husky/pre-push"

if [ ! -f "$HOOK_FILE" ]; then
    echo "FAIL - $HOOK_FILE not found (cannot run any case in this file)"
    exit 1
fi

# ---------------------------------------------------------------------------
# Case 1 (tripwire): every value-assignment to PREPUSH_RUN_BACKEND in the
# live file, by exact count and shape. Anchors on end-of-line so it does not
# false-match the many prose/echo lines that MENTION the variable's name
# without assigning it (verified: 0 of those end a line in "=0" or "=1").
#
#   - exactly ONE bare (unindented) seed, and it must be 0 — a future edit
#     reverting this to 1 is the single biggest regression this file exists
#     to prevent.
#   - exactly FOUR total assignments in the whole file: the seed (0), the
#     PREPUSH_FULL=1 branch (1), the PREPUSH_PATHAWARE=0 branch (1), and the
#     classifier's skip-backend branch (0). A FIFTH assignment anywhere
#     else — e.g. a "full" verdict silently regaining an explicit `=1` —
#     would reintroduce the exact lock-contention regression measured above.
# ---------------------------------------------------------------------------
seed_matches="$(grep -n '^PREPUSH_RUN_BACKEND=0$' "$HOOK_FILE" || true)"
seed_count="$(printf '%s\n' "$seed_matches" | grep -c '.' || true)"
[ -z "$seed_matches" ] && seed_count=0
if [ "$seed_count" -eq 1 ]; then
    note_pass "tripwire — exactly one bare top-level seed 'PREPUSH_RUN_BACKEND=0' ($seed_matches)"
else
    note_fail "tripwire — expected exactly one bare 'PREPUSH_RUN_BACKEND=0' seed, found $seed_count: $seed_matches"
fi

old_seed_count="$(grep -c '^PREPUSH_RUN_BACKEND=1$' "$HOOK_FILE" || true)"
if [ "${old_seed_count:-0}" -eq 0 ]; then
    note_pass "tripwire — no bare top-level 'PREPUSH_RUN_BACKEND=1' seed (the old default) anywhere in the file"
else
    note_fail "tripwire — a bare top-level 'PREPUSH_RUN_BACKEND=1' reappeared ($old_seed_count occurrence(s)) — the old default is back"
fi

total_assigns="$(grep -c 'PREPUSH_RUN_BACKEND=[01]$' "$HOOK_FILE" || true)"
if [ "${total_assigns:-0}" -eq 4 ]; then
    note_pass "tripwire — exactly 4 value-assignments to PREPUSH_RUN_BACKEND (seed + FULL branch + PATHAWARE branch + skip-backend branch)"
else
    note_fail "tripwire — expected exactly 4 PREPUSH_RUN_BACKEND=[01] assignments, found $total_assigns — a stray assignment (e.g. the classifier's 'full' verdict silently setting =1 again) would reintroduce default-on behaviour"
fi

# ---------------------------------------------------------------------------
# Case 2 (GUILT, behavioural, real code): extract the live path-aware block
# and execute it with a stub classifier answering "full" — a diff that DOES
# touch backend-relevant paths. Under the new default this must still leave
# PREPUSH_RUN_BACKEND at 0: the classifier's verdict no longer gates local
# execution by itself.
# ---------------------------------------------------------------------------
extract_pathaware_block() {
    sed -n '/^if \[ "\${PREPUSH_FULL:-0}" = "1" \]; then$/,/^fi$/p' "$HOOK_FILE"
}

block_text="$(extract_pathaware_block)"
block_lines="$(printf '%s\n' "$block_text" | wc -l | tr -d ' ')"
if [ -z "$block_text" ] || [ "${block_lines:-0}" -lt 20 ]; then
    note_fail "extraction — could not extract the path-aware block from $HOOK_FILE (got $block_lines lines) — re-anchor this test"
    echo "---"
    echo "$pass passed, $fail failed"
    exit 1
fi
note_pass "extraction — path-aware block extracted from the live hook ($block_lines lines)"

# $1 = block text to execute (allows Case 7 to run a MUTATED copy through
#      the exact same harness as the real block, instead of duplicating it)
# $2 = remote name to pass as positional $1 ("origin" for the real path)
# $3 = PREPUSH_FULL env value (or unset)
# $4 = PREPUSH_PATHAWARE env value (or unset)
# $5 = classifier stub verdict ("full" | "skip-backend" | "crash")
run_pathaware_block_with_text() {
    _text="$1"
    _remote="$2"
    _full="${3:-}"
    _pathaware="${4:-}"
    _verdict="$5"

    _td="$(mktemp -d)"
    _classifier="$_td/classify.py"
    case "$_verdict" in
        crash)
            printf '#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n' > "$_classifier"
            ;;
        *)
            printf '#!/usr/bin/env python3\nprint("%s")\n' "$_verdict" > "$_classifier"
            ;;
    esac

    _refs="$_td/refs"
    _head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
    printf 'refs/heads/test-branch %s refs/heads/test-branch %s\n' "$_head" "$_head" > "$_refs"

    _out="$_td/script.sh"
    {
        echo 'set -e'
        echo "cd \"$REPO_ROOT\""
        echo "PREPUSH_RUN_BACKEND=0"
        echo "PREPUSH_CLASSIFIER=\"$_classifier\""
        echo "PREPUSH_REFS=\"$_refs\""
        [ -n "$_full" ] && echo "PREPUSH_FULL=\"$_full\""
        [ -n "$_pathaware" ] && echo "PREPUSH_PATHAWARE=\"$_pathaware\""
        printf '%s\n' "$_text"
        echo 'echo "RESULT_RUN_BACKEND=$PREPUSH_RUN_BACKEND"'
    } > "$_out"

    sh -e "$_out" "$_remote" 2>&1
    _rc=$?
    rm -rf "$_td"
    return $_rc
}

# Thin wrapper over the REAL, unmutated block — used by every case except
# Case 7's mutant.
run_pathaware_block() {
    run_pathaware_block_with_text "$block_text" "$1" "${2:-}" "${3:-}" "$4"
}

out2="$(run_pathaware_block origin "" "" full)"
if printf '%s\n' "$out2" | grep -q '^RESULT_RUN_BACKEND=0$'; then
    note_pass "GUILT — classifier verdict 'full' (backend WAS touched) still leaves PREPUSH_RUN_BACKEND=0 by default"
else
    note_fail "GUILT — expected PREPUSH_RUN_BACKEND=0 on a 'full' verdict, got: $out2"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence, same mechanism): a clean 'skip-backend' verdict must
# ALSO still leave PREPUSH_RUN_BACKEND=0 — the ordinary, already-existing
# behaviour, unperturbed by this diff.
# ---------------------------------------------------------------------------
out3="$(run_pathaware_block origin "" "" skip-backend)"
if printf '%s\n' "$out3" | grep -q '^RESULT_RUN_BACKEND=0$'; then
    note_pass "innocence — classifier verdict 'skip-backend' still leaves PREPUSH_RUN_BACKEND=0 (unchanged behaviour)"
else
    note_fail "innocence — expected PREPUSH_RUN_BACKEND=0 on a 'skip-backend' verdict, got: $out3"
fi

# ---------------------------------------------------------------------------
# Case 4 (innocence, ambiguous/error path): a crashing classifier is the
# OLD fail-closed-to-FULL trigger. Under the new default it must still not
# run the suite locally (CI is the real gate regardless of ambiguity now) —
# but it must NOT silently die either; the block itself must still exit 0
# (the ambiguity is reported via stderr, never a hard failure at this
# stage) and PREPUSH_RUN_BACKEND must still read 0.
# ---------------------------------------------------------------------------
out4="$(run_pathaware_block origin "" "" crash)"
if printf '%s\n' "$out4" | grep -q '^RESULT_RUN_BACKEND=0$'; then
    note_pass "innocence — a crashing/ambiguous classifier still leaves PREPUSH_RUN_BACKEND=0 (CI is the real gate now, not local ambiguity-driven full-run)"
else
    note_fail "innocence — expected PREPUSH_RUN_BACKEND=0 on a crashing classifier, got: $out4"
fi
if printf '%s\n' "$out4" | grep -qi 'fail.closed'; then
    note_pass "innocence — the ambiguity is still reported (a 'fail closed' diagnostic line is still printed)"
else
    note_fail "innocence — no 'fail closed' diagnostic was printed for a crashing classifier: $out4"
fi

# ---------------------------------------------------------------------------
# Case 5 (INNOCENCE 1 — the escape hatch, real code): PREPUSH_FULL=1 must
# still force PREPUSH_RUN_BACKEND=1 — this is the way back in, and per the
# ship instructions it must be proven by a test, not just left in place.
# Uses the SAME extracted block; only the env differs.
# ---------------------------------------------------------------------------
out5="$(run_pathaware_block origin 1 "" full)"
if printf '%s\n' "$out5" | grep -q '^RESULT_RUN_BACKEND=1$'; then
    note_pass "INNOCENCE 1 — PREPUSH_FULL=1 still forces PREPUSH_RUN_BACKEND=1"
else
    note_fail "INNOCENCE 1 — PREPUSH_FULL=1 did not force PREPUSH_RUN_BACKEND=1, got: $out5"
fi

# ---------------------------------------------------------------------------
# Case 6 (innocence, sibling escape hatch): PREPUSH_PATHAWARE=0's own
# documented contract is "same net effect as PREPUSH_FULL=1" — must also
# still force PREPUSH_RUN_BACKEND=1.
# ---------------------------------------------------------------------------
out6="$(run_pathaware_block origin "" 0 full)"
if printf '%s\n' "$out6" | grep -q '^RESULT_RUN_BACKEND=1$'; then
    note_pass "innocence — PREPUSH_PATHAWARE=0 still forces PREPUSH_RUN_BACKEND=1 (its documented contract)"
else
    note_fail "innocence — PREPUSH_PATHAWARE=0 did not force PREPUSH_RUN_BACKEND=1, got: $out6"
fi

# ---------------------------------------------------------------------------
# Case 7 (MUTATION CHECK on Case 2, the GUILT case — proves it actually
# exercises live code, not a no-op). Reintroduces the OLD behaviour directly
# into the extracted block: a "full" verdict forcing PREPUSH_RUN_BACKEND=1,
# spliced in right where the block's own trailing comment says a "full"
# verdict now does nothing. Re-runs EXACTLY Case 2's scenario (seed 0, no
# override, classifier says "full") against this mutated copy. If Case 2's
# assertion is real, this must now report 1 — the pre-diff regression this
# whole change exists to remove — proving the test is not vacuously true.
#
# `diff` confirms the mutation actually attached (measured scar, same
# night: a "surviving mutant" that turned out to be a substitution that was
# never applied — read the diff BEFORE trusting the mutant's exit code).
# ---------------------------------------------------------------------------
_mutation_anchor='        # VERDICT_OUTPUT = "full": PREPUSH_RUN_BACKEND stays at its default —'
mutated_guilt_block="$(printf '%s\n' "$block_text" | awk -v anchor="$_mutation_anchor" '
    $0 == anchor { print "        [ \"$VERDICT_OUTPUT\" = \"full\" ] && PREPUSH_RUN_BACKEND=1" }
    { print }
')"

_mutdiff_td="$(mktemp -d)"
printf '%s\n' "$block_text" > "$_mutdiff_td/orig"
printf '%s\n' "$mutated_guilt_block" > "$_mutdiff_td/mutated"
mut_added_lines="$(diff "$_mutdiff_td/orig" "$_mutdiff_td/mutated" | grep -c '^>' || true)"
rm -rf "$_mutdiff_td"
if [ "${mut_added_lines:-0}" -ne 1 ]; then
    note_fail "mutation setup — expected the mutation to ADD exactly 1 line, diff shows $mut_added_lines added — mutation did not attach at the intended anchor, Case 7's verdict would be meaningless"
else
    note_pass "mutation setup — confirmed via diff: the mutation added exactly 1 line (a 'full' verdict forcing PREPUSH_RUN_BACKEND=1 again, the pre-diff behaviour)"

    out7="$(run_pathaware_block_with_text "$mutated_guilt_block" origin "" "" full)"
    if printf '%s\n' "$out7" | grep -q '^RESULT_RUN_BACKEND=1$'; then
        note_pass "mutation kills — Case 2's exact scenario against the mutated block reports RESULT_RUN_BACKEND=1 (the pre-diff regression), proving Case 2 would have failed against this shape — it is not vacuously true"
    else
        note_fail "mutation survived — Case 2's scenario against the mutated block still reports 0, expected the mutation to flip it to 1: $out7"
    fi
fi

# ---------------------------------------------------------------------------
# Case 8 (INNOCENCE 2, structural tripwire): the honest-verdict fail-closed
# guard at the bottom of the hook is exercised end-to-end by
# scripts/tests/test_prepush_honest_verdict.py (test_required_but_never_ran_says_unverified
# and friends) — not re-derived here. This case only pins that the guard's
# condition text is still exactly what it was before this diff, so a silent
# drift there would show up as a diff-review flag even though this file
# does not re-run that guard's own logic.
# ---------------------------------------------------------------------------
if grep -q 'if \[ "\$PREPUSH_RUN_BACKEND" = "1" \] && \[ "\${BACKEND_SUITE_RAN:-0}" != "1" \]; then' "$HOOK_FILE"; then
    note_pass "INNOCENCE 2 — the honest-verdict fail-closed guard condition is present, unchanged, byte-identical to before this diff (exercised by test_prepush_honest_verdict.py)"
else
    note_fail "INNOCENCE 2 — the honest-verdict fail-closed guard condition text has changed or disappeared — re-run scripts/tests/test_prepush_honest_verdict.py and re-anchor both files"
fi

# ---------------------------------------------------------------------------
# Case 9 (INNOCENCE 3, real code, top of file): the fast checks ahead of the
# path-aware block — the trusted-helper-bundle guard — still run and still
# block regardless of PREPUSH_RUN_BACKEND. Executes the REAL top of the live
# hook (lines 1-22) against a deliberately incomplete helper bundle.
# ---------------------------------------------------------------------------
top_of_file="$(sed -n '1,22p' "$HOOK_FILE")"
if ! printf '%s\n' "$top_of_file" | grep -q 'pre-push trusted helper bundle is incomplete'; then
    note_fail "extraction (Case 9) — expected the trusted-helper-bundle guard in the first 22 lines of $HOOK_FILE — re-anchor this test"
else
    _td9="$(mktemp -d)"
    _out9="$_td9/script.sh"
    {
        echo 'set -e'
        echo "cd \"$_td9\""
        # No scripts/ directory here at all -> the bundle is incomplete.
        printf '%s\n' "$top_of_file"
        echo 'echo "UNREACHABLE"'
    } > "$_out9"
    out9="$(sh "$_out9" 2>&1)"
    rc9=$?
    rm -rf "$_td9"
    if [ "$rc9" != "0" ] && printf '%s\n' "$out9" | grep -q 'trusted helper bundle is incomplete' \
        && ! printf '%s\n' "$out9" | grep -q 'UNREACHABLE'; then
        note_pass "INNOCENCE 3 — the trusted-helper-bundle guard at the top of the real hook still blocks (rc=$rc9), independent of the backend-suite default"
    else
        note_fail "INNOCENCE 3 — expected a non-zero exit + the incomplete-bundle message + no UNREACHABLE, got rc=$rc9 out='$out9'"
    fi
fi

echo "---"
echo "$pass passed, $fail failed"

if [ "$fail" -eq 0 ]; then
    exit 0
else
    exit 1
fi
