#!/usr/bin/env python3
"""Guilt + innocence suite for the `.husky/pre-push` final-verdict branch.

WHY (measured live on Mini, 2026-07-27 — cicatrix-superscar.md family #2,
"esiste ≠ armato"): the path-aware gate can decide the backend suite is
REQUIRED for a diff, four separate environment gates can then skip the suite
entirely (no local PG / unprovisioned test DB / no venv / DB clone failed), and
before this fix all four fell through to the same closing line:

    🧭 6/6 changed file(s) are NOT on the innocent allowlist — running FULL suite
    🐍 Running Python tests...
    ⏭️  SKIP Python tests — local PG up but 'nuzantara_test' not provisioned
    ✅ All pre-push checks passed!

Mini's local PG had no `test` role at all, so EVERY push ever made from that
machine met a gate that ran zero tests and announced a pass. The skip is
legitimate (a machine without a test DB must still be able to push, and the
merge queue re-tests every entry against main); the CLAIM was not.

The condition is extracted LIVE from .husky/pre-push and evaluated by a real
`sh`, so this test breaks the moment the guard drifts from what actually runs —
never a Python reimplementation that could diverge in semantics.

Run:  python3 scripts/tests/test_prepush_honest_verdict.py
      pytest scripts/tests/test_prepush_honest_verdict.py -q
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK_FILE = REPO_ROOT / ".husky" / "pre-push"


def _hook_text() -> str:
    return HOOK_FILE.read_text()


def _extract_verdict_condition() -> str:
    """The real `if` condition guarding the NOT-VERIFIED verdict."""
    m = re.search(
        r'^if (\[ "\$PREPUSH_RUN_BACKEND" = "1" \] && \[ "\$\{BACKEND_SUITE_RAN:-0\}" != "1" \]); then$',
        _hook_text(),
        re.MULTILINE,
    )
    assert m, (
        f"final-verdict condition not found in {HOOK_FILE}. It must stay a "
        "single-line `if` so this test can evaluate the REAL expression."
    )
    return m.group(1)


def _verdict(run_backend: str, suite_ran: str | None) -> str:
    """Evaluate the extracted condition under a real `sh -e`, exactly as the
    hook runs it. `suite_ran=None` models the variable being UNSET — the
    path-aware-skip path never enters the block that initialises it."""
    cond = _extract_verdict_condition()
    assign = "" if suite_ran is None else f'BACKEND_SUITE_RAN="{suite_ran}"\n'
    script = (
        "set -e\n"
        f'PREPUSH_RUN_BACKEND="{run_backend}"\n'
        f"{assign}"
        f"if {cond}; then echo UNVERIFIED; else echo PASSED; fi\n"
    )
    r = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, f"condition aborted the shell: {r.stderr!r}"
    return r.stdout.strip()


# --------------------------------------------------------------------------
# GUILT: the exact Mini shape must NOT be reported as a pass.
# --------------------------------------------------------------------------


def test_required_but_never_ran_is_not_a_pass() -> None:
    assert _verdict("1", "0") == "UNVERIFIED"


def test_required_but_variable_left_unset_is_not_a_pass() -> None:
    """Fail-safe direction: if some future skip path forgets to touch the
    bookkeeping at all, the verdict must still refuse to claim a pass."""
    assert _verdict("1", None) == "UNVERIFIED"


# --------------------------------------------------------------------------
# INNOCENCE: the two legitimate greens must stay green.
# --------------------------------------------------------------------------


def test_suite_actually_ran_is_a_pass() -> None:
    assert _verdict("1", "1") == "PASSED"


def test_path_aware_skip_is_a_pass() -> None:
    """A diff with no backend-relevant paths never needed the suite: reporting
    it as unverified would cry wolf on every docs/frontend push and train
    people to ignore the warning."""
    assert _verdict("0", None) == "PASSED"


# --------------------------------------------------------------------------
# STRUCTURE: every skip path must record WHY, and exactly one path may claim
# the suite ran. These are the invariants a 5th skip branch could break.
# --------------------------------------------------------------------------


def test_every_suite_skip_branch_records_a_reason() -> None:
    text = _hook_text()
    skips = len(re.findall(r'echo "⏭️\s+SKIP Python tests', text))
    reasons = len(re.findall(r"^\s*BACKEND_SUITE_SKIP_REASON=", text, re.MULTILINE))
    assert skips > 0, "no 'SKIP Python tests' branches found — re-anchor this test"
    # One initialiser (empty) + one assignment per skip branch.
    assert reasons == skips + 1, (
        f"{skips} 'SKIP Python tests' branches but {reasons} "
        "BACKEND_SUITE_SKIP_REASON assignments (expected skips + 1 initialiser). "
        "A skip branch that records no reason produces the verdict "
        "'reason not recorded', which is the vague-alert failure mode: it tells "
        "the reader something is wrong but not what to fix."
    )


def test_only_the_passing_suite_claims_it_ran() -> None:
    text = _hook_text()
    assert len(re.findall(r"^\s*BACKEND_SUITE_RAN=1$", text, re.MULTILINE)) == 1, (
        "BACKEND_SUITE_RAN=1 must be set in exactly ONE place — the branch "
        "where pytest exited 0. Any second assignment is a way for a push to "
        "claim a verdict it never earned."
    )


def test_signal_death_does_not_claim_the_suite_ran() -> None:
    """A SIGTERM'd suite (TEST_RC >= 128, the contention failure this fleet
    hits) exits 1 before reaching the verdict — it must never be able to fall
    through to a pass."""
    text = _hook_text()
    m = re.search(r'TERMINATED by signal \$TEST_SIGNAL.*?\n(.*?)\n\s*else', text, re.DOTALL)
    assert m, "signal-classification branch not found — re-anchor this test"
    assert "exit 1" in m.group(1)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
