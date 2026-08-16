#!/usr/bin/env bash
# test_codex_spalla_grep_c.sh — pins the W104-class `grep -c .` fix in
# .claude/scripts/codex-spalla.sh (2026-08-14, class-audit per W89): `grep -c .`
# ALWAYS prints a valid count to stdout, including "0" on zero matches, but
# STILL exits 1 on zero matches — under this script's own `set -o pipefail`
# (codex-spalla.sh line 24), a zero-match pipeline counts as "failed", so the
# old `|| echo 0` fallback fired TOO, appending a second "0" after the one
# grep had already printed. On an empty diff the captured value was the
# two-line string "0\n0", which then broke `$((...))` arithmetic downstream
# (TOTAL_FILES=$((FILES_CHANGED + UNCOMMITTED_FILES + UNTRACKED_FILES))) with
# a hard `syntax error in expression`. Found by an independent spalla-review
# agent while reviewing an unrelated PR (attempting to invoke this script's
# sibling codex-second-opinion tooling); fixed by swapping the fallback from
# `|| echo 0` to `|| true` at BOTH call sites in the file (UNCOMMITTED_FILES
# and UNTRACKED_TOTAL_FOR_DUMP — the second was dead code with no downstream
# reader at fix time, but carried the identical defect shape).
#
# Section 1 (GUILT) proves the defect class is real and reproducible,
# standalone, never against the real file (which is already fixed).
# Section 2 (INNOCENCE) extracts and EXECUTES the actual assignment lines
# from the real file — not a hand-copied lookalike that could drift from
# what it's supposed to protect — against controlled empty/non-empty inputs,
# so a future regression that reintroduces `|| echo 0` fails this test
# directly.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
TARGET="$REPO_ROOT/.claude/scripts/codex-spalla.sh"
[ -f "$TARGET" ] || { echo "FAIL: target not found at $TARGET"; exit 2; }

FAILED=0
ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

# ── 1. GUILT: the historical broken pattern really does double-print and
#    really does break arithmetic on empty input — the bug class is not
#    hypothetical. ────────────────────────────────────────────────────────
broken_out="$(bash -euo pipefail -c 'printf "" | grep -c . 2>/dev/null || echo 0')"
if [ "$broken_out" = "$(printf '0\n0')" ]; then
    ok "historical '|| echo 0' pattern reproducibly double-prints '0\\n0' on empty input"
else
    bad "could not reproduce the historical double-print (got: $(printf '%q' "$broken_out")) — guilt fixture may be stale"
fi

broken_arith_rc=0
bash -euo pipefail -c 'X="$(printf "" | grep -c . 2>/dev/null || echo 0)"; TOTAL=$((X + 0))' >/dev/null 2>&1 || broken_arith_rc=$?
if [ "$broken_arith_rc" -ne 0 ]; then
    ok "historical pattern reproducibly breaks \$(( )) arithmetic on empty input (rc=$broken_arith_rc)"
else
    bad "historical pattern unexpectedly did NOT break arithmetic (rc=0) — guilt fixture may be stale"
fi

# ── 2. INNOCENCE: extract the two REAL fixed lines from the file and run
#    them against controlled empty/non-empty inputs — must be a clean single
#    value each time. ───────────────────────────────────────────────────────
extract_line() { grep -m1 "$1" "$TARGET"; }

uncommitted_line="$(extract_line '^UNCOMMITTED_FILES=')"
[ -n "$uncommitted_line" ] || { echo "FAIL: UNCOMMITTED_FILES assignment not found in $TARGET"; exit 2; }
if printf '%s\n' "$uncommitted_line" | grep -qE '\|\|[[:space:]]*echo[[:space:]]+0'; then
    bad "UNCOMMITTED_FILES line still contains the buggy '|| echo 0' fallback: $uncommitted_line"
else
    ok "UNCOMMITTED_FILES line no longer contains '|| echo 0'"
fi

untracked_line="$(extract_line '^UNTRACKED_TOTAL_FOR_DUMP=')"
[ -n "$untracked_line" ] || { echo "FAIL: UNTRACKED_TOTAL_FOR_DUMP assignment not found in $TARGET"; exit 2; }
if printf '%s\n' "$untracked_line" | grep -qE '\|\|[[:space:]]*echo[[:space:]]+0'; then
    bad "UNTRACKED_TOTAL_FOR_DUMP line still contains the buggy '|| echo 0' fallback: $untracked_line"
else
    ok "UNTRACKED_TOTAL_FOR_DUMP line no longer contains '|| echo 0'"
fi

# Execute the ACTUAL extracted lines (not a hand-copy) against a real
# throwaway git repo, so the assertion is against the file's own logic.
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/codexspalla-grepc.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
git -C "$SANDBOX" init -q
git -C "$SANDBOX" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init

run_uncommitted() {
    ( cd "$SANDBOX" && eval "$uncommitted_line" && printf '%s' "$UNCOMMITTED_FILES" )
}

out_empty="$(run_uncommitted)"
lines_empty="$(printf '%s' "$out_empty" | wc -l | tr -d ' ')"
if [ "$out_empty" = "0" ] && [ "$lines_empty" -eq 0 ]; then
    ok "UNCOMMITTED_FILES on a clean repo -> single clean '0'"
else
    bad "UNCOMMITTED_FILES on a clean repo -> expected single '0', got $(printf '%q' "$out_empty") ($lines_empty extra newline(s))"
fi

echo one >> "$SANDBOX/a.txt"; git -C "$SANDBOX" add a.txt >/dev/null; git -C "$SANDBOX" commit -q -m a
echo two >> "$SANDBOX/b.txt"; git -C "$SANDBOX" add b.txt >/dev/null; git -C "$SANDBOX" commit -q -m b
echo changed >> "$SANDBOX/a.txt"
echo changed >> "$SANDBOX/b.txt"
out_two="$(run_uncommitted)"
if [ "$out_two" = "2" ]; then
    ok "UNCOMMITTED_FILES with 2 modified files -> '2'"
else
    bad "UNCOMMITTED_FILES with 2 modified files -> expected '2', got $(printf '%q' "$out_two")"
fi

# UNTRACKED_TOTAL_FOR_DUMP reads from a shell variable, not a git command —
# exercise it directly with an empty and a populated value, matching how the
# real script populates UNTRACKED_FILES_FOR_DUMP just above it.
run_untracked_total() {
    ( UNTRACKED_FILES_FOR_DUMP="$1"; eval "$untracked_line"; printf '%s' "$UNTRACKED_TOTAL_FOR_DUMP" )
}

out_ut_empty="$(run_untracked_total "")"
lines_ut_empty="$(printf '%s' "$out_ut_empty" | wc -l | tr -d ' ')"
if [ "$out_ut_empty" = "0" ] && [ "$lines_ut_empty" -eq 0 ]; then
    ok "UNTRACKED_TOTAL_FOR_DUMP on empty var -> single clean '0'"
else
    bad "UNTRACKED_TOTAL_FOR_DUMP on empty var -> expected single '0', got $(printf '%q' "$out_ut_empty") ($lines_ut_empty extra newline(s))"
fi

out_ut_three="$(run_untracked_total "$(printf 'x.txt\ny.txt\nz.txt')")"
if [ "$out_ut_three" = "3" ]; then
    ok "UNTRACKED_TOTAL_FOR_DUMP with 3 paths -> '3'"
else
    bad "UNTRACKED_TOTAL_FOR_DUMP with 3 paths -> expected '3', got $(printf '%q' "$out_ut_three")"
fi

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — codex-spalla.sh grep -c fix"; exit 0; } || { echo "FAIL — codex-spalla.sh grep -c fix"; exit 1; }
