#!/usr/bin/env python3
"""observe_visa_check_catalogue_e33.py — bites: observation for CAT-visa-check-e33-e33g.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is `match_tree._reason()` via `recommend_visa()` behind
`POST /api/visa/match` on `nuzantara-rag`, which reads `VISA_META[...].notes` and
`VISA_META[...].purposes` from `catalogue.py`. The observation runs `test_catalogue.py`
and `test_match_tree.py` and requires:
1. Every test in both files to pass (`summary_ok` with floor `MIN_TESTS = 55`);
2. All required E33/E33G catalogue and match-tree tests to be reported as `PASSED`
   in the run output (`required_names_ok`).
"""

# bites-observable — no arguments; one literal program, literal test targets.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "apps" / "backend-rag"
TEST_TARGETS: tuple[str, ...] = (
    "backend/tests/services/visa_check/test_catalogue.py",
    "backend/tests/services/visa_check/test_match_tree.py",
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Exact test count across TEST_TARGETS (no parametrize expansions in either file):
# - test_catalogue.py: 15 existing (TestEnumStability 3 + TestVisaMetaCompleteness 3
#   + TestSeedAgreement 4 + TestDerivedDicts 4 + TestPurposeCoverage 1)
#   + 4 new in TestE33Notes = 19 tests.
# - test_match_tree.py: 32 existing (TestRankedShape 4 + TestBackwardsCompatProperties 3
#   + TestOther 1 + TestLongTourism 3 + TestWorkRemote 4 + TestInvestor 3
#   + TestSimpleBranches 6 + TestPreArrivalSteps 1 + TestCoverageSweep 1
#   + TestPreArrivalStepsBelongToTheRecommendedVisa 6)
#   + 3 new in TestWorkRemote + 1 new in TestInvestor (plus 1 TestInvestor test
#   renamed in place) = 36 tests.
# Total = 19 + 36 = 55 tests.
MIN_TESTS = 55
TIMEOUT_SECONDS = 240

REQUIRED_TESTS: tuple[str, ...] = (
    "TestE33Notes::test_e33_notes_state_rangkap_kegiatan_and_not_non_working",
    "TestE33Notes::test_e33g_notes_state_annual_income_from_signed_pack_and_not_savings",
    "TestE33Notes::test_e33g_purposes_is_work_remote_only",
    "TestE33Notes::test_e33_and_e33g_innocence_invariants_preserved",
    "TestWorkRemote::test_mid_budget_e33g_reason_states_annual_income_not_savings",
    "TestWorkRemote::test_mid_budget_e33g_steps_state_annual_income_not_balance",
    "TestWorkRemote::test_over_budget_e33g_steps_state_annual_income_not_balance",
    "TestInvestor::test_mid_budget_ranking_excludes_e33g",
    "TestInvestor::test_under_budget_referral_names_no_visa_code_and_no_savings",
)

_SUMMARY = re.compile(
    r"^(?:=+ )?(\d+) passed(?:, \d+ warnings?)? in [\d.]+s(?: \([\d:]+\))?(?: =+)?$"
)


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (warnings aside), N >= 55.

    Anything else (failed, error, skipped, xfailed, deselected, a reduced count,
    no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    if match is None:
        return False
    return int(match.group(1)) >= MIN_TESTS


def required_names_ok(output: str | None) -> bool:
    """True only when every test in REQUIRED_TESTS is listed as PASSED in output."""
    if not output:
        return False
    lines = [ln.strip() for ln in output.splitlines()]
    for name in REQUIRED_TESTS:
        pattern = re.compile(
            rf"^(?:PASSED\s+\S*?\b{re.escape(name)}\b|\S*?\b{re.escape(name)}\s+PASSED\b)"
        )
        if not any(pattern.search(ln) for ln in lines):
            return False
    return True


def _backend_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    try:
        result = subprocess.run(
            [
                _backend_python(),
                "-m",
                "pytest",
                # no -q: apps/backend-rag/pytest.ini addopts already sets it, and a
                # second -q trips scripts/pytest_guards/pytest_verbosity_guard.py
                "-rA",
                "-p",
                "no:cacheprovider",
                *TEST_TARGETS,
            ],
            cwd=BACKEND_DIR,
            env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            f"observe_visa_check_catalogue_e33: FAILED (timeout after {TIMEOUT_SECONDS}s)"
        )
        return 1

    out = ANSI.sub("", result.stdout + result.stderr)
    lines = [
        ln
        for ln in out.splitlines()
        if re.search(r"\d+ (passed|failed|error|skipped)", ln) and " in " in ln
    ]
    line = lines[-1] if lines else None
    summary = line.strip("= ") if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line) or not required_names_ok(out):
        print(f"observe_visa_check_catalogue_e33: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_check_catalogue_e33: {summary}")
    print("observe_visa_check_catalogue_e33: E33 and E33G catalogue notes hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
