#!/usr/bin/env python3
"""observe_visa_oracle_penjamin_copy.py — bites: observation for the retirement basis and income copy.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle interview. The observation runs the copy-truth
test file from `apps/mouth` and requires every test in it to pass, with the tests that
prove this change reported as run: the retirement basis options say penjamin (EN and ID)
and the income question says income or an allowance and carries no digit.
Exit 0 only if Vitest reports the file passed with zero failures.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/copy-truth.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MIN_TESTS = 70
# Each must be reported as run, so deleting one cannot hide behind the file total.
REQUIRED_TESTS = (
    "the basis options say penjamin and no longer say family sponsor",
    "the income question names income or an allowance and anchors on no figure",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 70.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= MIN_TESTS


def missing_tests(out: str) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in REQUIRED_TESTS if not any(t in l for l in passed)]


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
        print(f"observe_visa_oracle_penjamin_copy: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_penjamin_copy: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_penjamin_copy: {summary}")
    print("observe_visa_oracle_penjamin_copy: penjamin copy holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
