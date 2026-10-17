#!/usr/bin/env python3
"""observe_visa_oracle_own_shareholding_question.py - bites: observation for the E28A own-shareholding question.

# bites-observable - this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file.

The consumer is the public Visa Oracle interview (PT PMA investor path). The observation
runs the dedicated Vitest file from `apps/mouth` and requires every test to pass: the
question follows the paid-up capital question, has no not-sure option, is asked only on the
PT PMA investor path, maps 9999999999 to a known whole-rupiah value, and its EN and ID copy
names no threshold. Exit 0 only on a full pass of at least 6 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/own-shareholding-question.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


MIN_TESTS = 6
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 6.

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
        print(f"observe_visa_oracle_own_shareholding_question: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_own_shareholding_question: {summary}")
    print("observe_visa_oracle_own_shareholding_question: own shareholding question holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
