#!/usr/bin/env python3
"""observe_visa_oracle_e33_deposit_reason.py — bites: observation for the Second Home deposit reason.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs the
engine-adapter test file from `apps/mouth` and requires every test in it to pass:
a second_home / invest deposit of USD 130,000 or more that is not at a state bank
or not in the visitor's own name gets its own fact-derived reason (EN and ID),
while retirement walks and below-threshold deposits keep their existing copy.
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
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


MIN_TESTS = 100
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 8.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= MIN_TESTS


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", TEST_FILE],
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
        print(f"observe_visa_oracle_e33_deposit_reason: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_e33_deposit_reason: {summary}")
    print("observe_visa_oracle_e33_deposit_reason: e33 deposit reason holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
