#!/bin/sh
# test_prepush_failclosed.sh — regression test for the sh -e fail-closed
# defect in .husky/pre-push (scar W101, cicatrix-superscar.md famiglia #2).
#
# Husky's wrapper (.husky/_/h) executes every hook via `sh -e "$s"`. Under
# that errexit, a BARE command-substitution assignment
#   VAR="$(some_command)"
# aborts the WHOLE script the instant some_command exits non-zero — the
# assignment's exit status IS the command's exit status, and a plain
# assignment statement is not exempt from set -e the way an if/while
# condition or an AND/OR list is. Any code below that assignment meant to
# INSPECT the failure (a subsequent `$?` check, a fail-closed branch, a
# cleanup step) can therefore never run: the process is already dead.
#
# .husky/pre-push's own path-aware classifier gate documents "a non-zero
# classifier exit forces the FULL suite" — but until this fix, the bare
# `VERDICT_OUTPUT="$(...)"` assignment made that fallback dead code. Any
# worktree on a branch predating scripts/prepush_classify.py (missing file
# -> classifier exits non-zero) hard-blocked the push with husky's generic
# "code 2" instead of degrading to the full suite as documented.
#
# This script proves, at the shell-semantics level (no repo state needed),
# WHY the bug fires under the OLD pattern and that the NEW pattern
# (`VAR="$(cmd)" || VAR_RC=$?`) survives to let the fail-closed check run.
# It also tripwires the live hook file so the old bare pattern can never
# silently return on VERDICT_OUTPUT specifically.
#
# Run:  sh scripts/tests/test_prepush_failclosed.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

# ---------------------------------------------------------------------------
# Case 1 (guilt, NEW pattern): errexit-immune capture must survive a failing
# command substitution and let the script report the real exit code.
# ---------------------------------------------------------------------------
out1="$(sh -e -c 'RC=0; OUT="$(exit 2)" || RC=$?; echo "RC=$RC"' 2>/dev/null)"
if [ "$out1" = "RC=2" ]; then
    note_pass "guilt (NEW pattern) — script survives to report RC=2 (got: $out1)"
else
    note_fail "guilt (NEW pattern) — expected RC=2, got: $out1"
fi

# ---------------------------------------------------------------------------
# Case 2 (guilt, OLD pattern): documents WHY the fix is needed. A bare
# assignment with no || guard must abort BEFORE the next statement runs —
# "unreachable" must never be printed, and the sh -e process must exit
# non-zero.
# ---------------------------------------------------------------------------
out2="$(sh -e -c 'OUT="$(exit 2)"; echo "unreachable"' 2>/dev/null)"
rc2=$?
if [ "$rc2" != "0" ] && [ "$out2" != "unreachable" ]; then
    note_pass "guilt-2 (OLD pattern) — sh -e aborted before printing 'unreachable' (rc=$rc2, out='$out2')"
else
    note_fail "guilt-2 (OLD pattern) — expected non-zero exit and no 'unreachable' output, got rc=$rc2 out='$out2'"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence, NEW pattern): a SUCCEEDING command substitution must
# behave exactly as before — RC stays 0, OUT captures stdout normally. The
# `|| VAR_RC=$?` guard must not perturb the happy path.
# ---------------------------------------------------------------------------
out3="$(sh -e -c 'RC=0; OUT="$(echo full)" || RC=$?; echo "RC=$RC OUT=$OUT"' 2>/dev/null)"
if [ "$out3" = "RC=0 OUT=full" ]; then
    note_pass "innocence (NEW pattern) — happy path unperturbed (got: $out3)"
else
    note_fail "innocence (NEW pattern) — expected 'RC=0 OUT=full', got: $out3"
fi

# ---------------------------------------------------------------------------
# Case 4 (tripwire): grep the LIVE hook file — a bare unguarded
# VERDICT_OUTPUT="$(  ...  )" (no "|| VERDICT_RC=" on the same line) must
# never reappear. Anchors on the repo root two levels above this script.
# ---------------------------------------------------------------------------
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
HOOK_FILE="$REPO_ROOT/.husky/pre-push"

if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire — $HOOK_FILE not found (cannot verify)"
else
    # Bare pattern = the assignment opens with VERDICT_OUTPUT="$( but the
    # SAME line does not also contain the errexit-immune guard.
    bad_lines="$(grep -n 'VERDICT_OUTPUT="\$(' "$HOOK_FILE" | grep -v '|| VERDICT_RC=' || true)"
    if [ -z "$bad_lines" ]; then
        note_pass "tripwire — no bare unguarded VERDICT_OUTPUT=\"\$(...)\" in $HOOK_FILE"
    else
        note_fail "tripwire — bare unguarded VERDICT_OUTPUT assignment reintroduced in $HOOK_FILE: $bad_lines"
    fi
fi

echo "---"
echo "$pass passed, $fail failed"

if [ "$fail" -eq 0 ]; then
    exit 0
else
    exit 1
fi
