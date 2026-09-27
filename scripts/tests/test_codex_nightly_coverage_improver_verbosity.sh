#!/bin/sh
# test_codex_nightly_coverage_improver_verbosity.sh
#
# Regression test for the 2026-09-27 repair of
# scripts/codex/codex-nightly-coverage-improver.sh: its coverage-scan pytest
# invocation carried its own `-q`, ON TOP of the `-q` already set by
# apps/backend-rag/pytest.ini's addopts (the cwd this invocation runs from,
# scripts/codex/codex-nightly-coverage-improver.sh:114 `cd apps/backend-rag`).
# Two `-q` reach effective verbosity -2, where pytest prints no pass/fail
# tally at all — scripts/pytest_guards/pytest_verbosity_guard.py refuses that
# run with a UsageError before a single test collects.
#
# Measured live on Pro (com.nuzantara.codex-coverage-improver, 2026-09-20
# through 2026-09-27, one run/night at 03:00): every run logged "Coverage
# report failed to generate" and exited 1 — the guard's UsageError aborted
# pytest before backend/tests/services/rag/coverage-<date>.json could ever be
# written, and the wrapper's `|| true` on the pytest line swallowed the
# guard's own readable error, leaving only the generic downstream message.
#
# Two checks, matching the two ways this can regress:
#   1 (static)     — the live coverage-scan invocation must not carry its own
#                    quiet flag on top of the config's.
#   2 (functional) — the guard's real verdict, run for real against a
#                    synthetic root whose addopts already sets `-q` (same
#                    shape as apps/backend-rag/pytest.ini): the OLD command
#                    line (with the redundant `-q`) must still be rejected
#                    (guilt — proves this test would have caught the live
#                    regression), and the NEW one (without it) must pass with
#                    a readable tally (innocence).
#
# Run:  sh scripts/tests/test_codex_nightly_coverage_improver_verbosity.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0
note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="$SCRIPT_DIR/codex/codex-nightly-coverage-improver.sh"
GUARD="$REPO_ROOT/scripts/pytest_guards/pytest_verbosity_guard.py"

if [ ! -f "$TARGET" ]; then
    echo "FATAL: $TARGET not found"
    exit 1
fi
if [ ! -f "$GUARD" ]; then
    echo "FATAL: $GUARD not found"
    exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test-coverage-verbosity.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# ---------------------------------------------------------------------------
# Check 1 (static): the live coverage-scan pytest invocation must not carry
# a redundant `-q` on top of apps/backend-rag/pytest.ini's own addopts `-q`.
# ---------------------------------------------------------------------------
scan_block="$(grep -n -A5 'PYTHONPATH=\. timeout 600 pytest backend/tests/services/rag/' "$TARGET")"
case "$scan_block" in
    *' -q --tb=no'*|*'-q '*'--tb=no'*)
        note_fail "static: coverage-scan invocation still carries a redundant -q — found: $scan_block"
        ;;
    *)
        note_pass "static: coverage-scan invocation no longer duplicates the config's -q"
        ;;
esac
case "$scan_block" in
    *'--tb=no'*)
        note_pass "static: coverage-scan invocation still keeps --tb=no"
        ;;
    *)
        note_fail "static: coverage-scan invocation lost --tb=no entirely — found: $scan_block"
        ;;
esac

# ---------------------------------------------------------------------------
# Fixture: a synthetic pytest root whose addopts already sets `-q`, same
# shape as apps/backend-rag/pytest.ini (scripts/tests/test_pytest_verbosity_guard.py's
# own _make_root pattern, duplicated here rather than imported — this is a
# shell test, that one is a pytest module).
# ---------------------------------------------------------------------------
make_root() {
    rm -rf "$WORK/root"
    mkdir -p "$WORK/root/scripts/pytest_guards"
    cp "$GUARD" "$WORK/root/scripts/pytest_guards/pytest_verbosity_guard.py"
    cat > "$WORK/root/pytest.ini" <<'INI'
[pytest]
addopts =
    -q
INI
    cat > "$WORK/root/conftest.py" <<'CONFTEST'
from __future__ import annotations
import sys
from pathlib import Path
for _ancestor in Path(__file__).resolve().parents:
    _guards = _ancestor / "scripts" / "pytest_guards"
    if (_guards / "pytest_verbosity_guard.py").is_file():
        if str(_guards) not in sys.path:
            sys.path.insert(0, str(_guards))
        break
from pytest_verbosity_guard import pytest_configure  # noqa: E402,F401
CONFTEST
    cat > "$WORK/root/test_sample.py" <<'PYTEST'
def test_passes():
    assert True
PYTEST
}

# ---------------------------------------------------------------------------
# Check 2 (functional, guilt): the OLD invocation shape (redundant `-q` on
# top of the config's) must be rejected by the guard — proves this test
# would have caught the live Pro regression.
# ---------------------------------------------------------------------------
make_root
out_old="$(cd "$WORK/root" && python3 -m pytest --tb=no -q 2>&1)"
rc_old=$?
if [ "$rc_old" != "0" ] && printf '%s' "$out_old" | grep -q "effective verbosity is -2"; then
    note_pass "functional guilt: OLD invocation (redundant -q) is rejected by the guard (rc=$rc_old)"
else
    note_fail "functional guilt: expected guard rejection, got rc=$rc_old out=$out_old"
fi

# ---------------------------------------------------------------------------
# Check 3 (functional, innocence): the NEW invocation shape (no redundant
# -q) must pass, with a readable pass/fail tally.
# ---------------------------------------------------------------------------
make_root
out_new="$(cd "$WORK/root" && python3 -m pytest --tb=no 2>&1)"
rc_new=$?
if [ "$rc_new" = "0" ] && printf '%s' "$out_new" | grep -q "1 passed"; then
    note_pass "functional innocence: NEW invocation (no redundant -q) passes with a readable tally"
else
    note_fail "functional innocence: rc=$rc_new out=$out_new"
fi

echo
echo "TOTAL: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
