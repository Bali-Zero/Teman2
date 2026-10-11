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

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MIN_TESTS = 100
# Titles of the tests that prove this change; each must be reported as run, so
# deleting one cannot hide behind the file total staying above MIN_TESTS.
REQUIRED_TESTS = (
    "echoes a declared 2,999 and names the USD 3,000 minimum, EN and ID",
    "says a 'not sure' counted as zero instead of claiming a figure was given",
    "falls back to the static sentence, which also names the figure",
    "RETIREMENT_INCOME_THRESHOLD_USD tracks the signed pack's retirement-income hard filters",
    "E33E_RETIREMENT_ELIGIBLE's second figure (monthly income) is el.e33e.retirement's passive-income gte",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in required if not any(t in l for l in passed)]


def summary_ok(line: str | None, minimum: int = MIN_TESTS) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= minimum.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= minimum


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=verbose", TEST_FILE],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"^\s*Tests\s.*$", out, re.MULTILINE)
    line = tests.group(0) if tests else None
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_visa_oracle_retirement_reasons: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_retirement_reasons: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_retirement_reasons: adapter {summary}")
    print("observe_visa_oracle_retirement_reasons: retirement reasons hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
