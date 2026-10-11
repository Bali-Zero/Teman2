#!/usr/bin/env python3
"""observe_visa_oracle_retirement_reasons.py — bites: observation for the retirement reasons.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs the
engine-adapter test file from `apps/mouth` and requires every test in it to pass,
including the tests that prove a retirement visitor below the passive-income
bound is told the figure the rules check (USD 3,000 a month, EN and ID), that a
"not sure" answer is said to count as zero, and that both figures (USD 3,000 a
month and the USD 50,000 deposit) are pinned to the newest signed pack.
Exit 0 only if Vitest reports a full pass with the required titles present.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
MIN_TESTS = 100
# Titles of the tests that prove this change; each must be reported as run, so
# deleting one cannot hide behind the file total staying above MIN_TESTS.
REQUIRED_TESTS = (
    "echoes a declared 2,999 and names the USD 3,000 minimum, EN and ID",
    "says a 'not sure' counted as zero instead of claiming a figure was given",
    "falls back to the neutral static sentence",
    "keeps the retirement sentence when unrelated Second Home and paid-activity facts are also populated",
    "RETIREMENT_INCOME_THRESHOLD_USD tracks the signed pack's retirement-income hard filters",
    "E33E_RETIREMENT_ELIGIBLE's second figure (monthly income) is el.e33e.retirement's passive-income gte",
)


def missing_tests(report: dict, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required titles with no assertion whose status is exactly `passed`."""
    passed = [
        a.get("fullName", "")
        for f in report.get("testResults", [])
        for a in f.get("assertionResults", [])
        if a.get("status") == "passed"
    ]
    return [t for t in required if not any(t in name for name in passed)]


def summary_ok(report: dict | None, minimum: int = MIN_TESTS) -> bool:
    """True only for a report with every test passed and at least `minimum` of them.

    Failed, pending, todo, a reduced count or no report at all is False.
    """
    if not isinstance(report, dict):
        return False
    total = report.get("numTotalTests")
    passed = report.get("numPassedTests")
    if not isinstance(total, int) or not isinstance(passed, int):
        return False
    for key in ("numFailedTests", "numPendingTests", "numTodoTests"):
        if report.get(key, 0) != 0:
            return False
    return report.get("success") is True and passed == total and passed >= minimum


def parse_report(stdout: str) -> dict | None:
    """The Vitest JSON reporter's object: the stdout slice from the first brace."""
    start = stdout.find("{")
    if start < 0:
        return None
    try:
        return json.loads(stdout[start:])
    except ValueError:
        return None


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=json", TEST_FILE],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    report = parse_report(result.stdout)
    summary = (
        f"{report.get('numPassedTests')} passed of {report.get('numTotalTests')}"
        if report
        else "no Vitest JSON report"
    )
    if result.returncode != 0 or not summary_ok(report):
        print(f"observe_visa_oracle_retirement_reasons: FAILED ({summary})\n{result.stderr[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(report)
    if absent:
        print(f"observe_visa_oracle_retirement_reasons: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_retirement_reasons: adapter {summary}")
    print("observe_visa_oracle_retirement_reasons: retirement reasons hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
