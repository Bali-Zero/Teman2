#!/bin/sh
# test_codex_nightly_coverage_improver_pipefail.sh
#
# Regression test for the 2026-08-27 repair of
# scripts/codex/codex-nightly-coverage-improver.sh: under `set -euo
# pipefail`, `git diff --name-only ... | grep -v "/tests/" | wc -l` crashed
# the WHOLE SCRIPT the instant Codex behaved correctly (a test-only diff,
# which is the only kind this generator ever asks for) — grep exits 1 when
# it matches nothing, pipefail promotes that to the pipeline's exit status,
# and `set -e` killed the script one line after "Codex completed" was
# logged, before it ever reached push/PR-create.
#
# Measured live 2026-08-27 against ~/logs/codex-coverage-improver/launchd.out.log:
# 9 of the last 10 nightly runs logged "Codex completed" and then NOTHING
# else, ever, for that run — no push line, no PR line, no error. Zero PRs
# opened in at least 10 days. This is the "branches exist but never become
# PRs" symptom the R7 mandate reported.
#
# Two checks, matching the two ways this can regress:
#   1 (static)     — the live NON_TEST_CHANGES line in the script must not
#                    have reverted to the bare, unguarded grep pipeline.
#   2 (functional) — the actual computation, run for real against a real
#                    git repo, must survive BOTH the guilt shape (a real
#                    non-test file present — must still be DETECTED) and
#                    the innocence shape (zero non-test files — the
#                    everyday case that used to crash the whole script).
#
# Run:  sh scripts/tests/test_codex_nightly_coverage_improver_pipefail.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0
note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$SCRIPT_DIR/codex/codex-nightly-coverage-improver.sh"

if [ ! -f "$TARGET" ]; then
    echo "FATAL: $TARGET not found"
    exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test-coverage-pipefail.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# ---------------------------------------------------------------------------
# Check 1 (static): the live script's NON_TEST_CHANGES line must not be the
# bare pattern that crashes on a clean (test-only) diff.
# ---------------------------------------------------------------------------
live_line="$(grep -n 'NON_TEST_CHANGES=\$(git diff' "$TARGET" | head -1)"
case "$live_line" in
    *'{ grep -v "/tests/" || true; }'*)
        note_pass "static: NON_TEST_CHANGES line guards grep's 'nothing matched' exit"
        ;;
    *)
        note_fail "static: NON_TEST_CHANGES line no longer guarded — found: $live_line"
        ;;
esac

# ---------------------------------------------------------------------------
# Fixture: a tiny real repo with a branch holding one commit.
# ---------------------------------------------------------------------------
make_repo() {  # $1 = test-only ("1") or also-touches-source ("0")
    rm -rf "$WORK/repo"
    mkdir -p "$WORK/repo"
    git -C "$WORK/repo" init -q
    git -C "$WORK/repo" config user.email "test@example.com"
    git -C "$WORK/repo" config user.name "test"
    git -C "$WORK/repo" commit -q --allow-empty -m init
    git -C "$WORK/repo" branch -M main
    mkdir -p "$WORK/repo/backend/tests" "$WORK/repo/backend/agents/services"
    printf 'x = 1\n' > "$WORK/repo/backend/tests/test_foo.py"
    git -C "$WORK/repo" add -A
    if [ "$1" = "0" ]; then
        printf 'y = 2\n' > "$WORK/repo/backend/agents/services/foo.py"
        git -C "$WORK/repo" add -A
    fi
    git -C "$WORK/repo" checkout -q -b "codex/coverage-foo-20260827_030000"
    git -C "$WORK/repo" commit -q -m "test(foo): improve coverage via Codex nightly"
}

# The exact expression from the FIXED script (line extracted at test-write
# time; kept literal here rather than re-sourcing the whole script, which
# would require faking every env var and external tool it depends on).
run_fixed_expression() {
    ( cd "$WORK/repo" && set -euo pipefail
      NON_TEST_CHANGES=$(git diff --name-only "main..codex/coverage-foo-20260827_030000" | { grep -v "/tests/" || true; } | wc -l | tr -d ' ')
      echo "NON_TEST_CHANGES=$NON_TEST_CHANGES"
      echo "REACHED_END" )
}

run_broken_expression() {
    ( cd "$WORK/repo" && set -euo pipefail
      NON_TEST_CHANGES=$(git diff --name-only "main..codex/coverage-foo-20260827_030000" | grep -v "/tests/" | wc -l | tr -d ' ')
      echo "NON_TEST_CHANGES=$NON_TEST_CHANGES"
      echo "REACHED_END" )
}

# ---------------------------------------------------------------------------
# Check 2 (functional, innocence): test-only diff — the everyday case that
# used to crash the whole script — must survive and report 0.
# ---------------------------------------------------------------------------
make_repo 1
out="$(run_fixed_expression 2>&1)"
rc=$?
if [ "$rc" = "0" ] && printf '%s' "$out" | grep -q "NON_TEST_CHANGES=0" \
    && printf '%s' "$out" | grep -q "REACHED_END"; then
    note_pass "functional innocence: test-only diff survives under set -euo pipefail (rc=0, count=0)"
else
    note_fail "functional innocence: rc=$rc out=$out"
fi

# Prove the OLD (bare) expression really does die on exactly this input —
# otherwise Check 2 above would be meaningless (asserting a non-bug).
out_broken="$(run_broken_expression 2>&1)"
rc_broken=$?
if [ "$rc_broken" != "0" ] && ! printf '%s' "$out_broken" | grep -q "REACHED_END"; then
    note_pass "regression proof: the OLD bare pattern really does crash on a test-only diff (rc=$rc_broken)"
else
    note_fail "regression proof: the OLD pattern was expected to crash on this input but didn't (rc=$rc_broken, out=$out_broken) — Check 2 above would not be testing anything"
fi

# ---------------------------------------------------------------------------
# Check 3 (functional, guilt): a diff that ALSO touches a non-test file must
# still be correctly counted and DETECTED — the fix must not blind the
# constraint it is guarding.
# ---------------------------------------------------------------------------
make_repo 0
out="$(run_fixed_expression 2>&1)"
rc=$?
if [ "$rc" = "0" ] && printf '%s' "$out" | grep -q "NON_TEST_CHANGES=1" \
    && printf '%s' "$out" | grep -q "REACHED_END"; then
    note_pass "functional guilt: a real non-test file is still counted correctly (count=1), not swallowed by the fix"
else
    note_fail "functional guilt: rc=$rc out=$out"
fi

echo
echo "TOTAL: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
