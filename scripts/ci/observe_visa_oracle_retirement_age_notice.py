#!/usr/bin/env python3
"""observe_visa_oracle_retirement_age_notice.py — bites: observation for the retirement age notice.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file.

The consumer is the public Visa Oracle interview. The observation runs the shell test
file from `apps/mouth` and requires every test in it to pass: a retirement visitor below
55 sees the notice right after the purpose answers (EN and ID), Continue reaches the
retirement branch, Second Home opens its branch, and a visitor of 55 or more never sees it.
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
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_components/OracleShell.retirement-age.test.tsx"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


MIN_TESTS = 5
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 5.

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
        print(f"observe_visa_oracle_retirement_age_notice: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_retirement_age_notice: {summary}")
    print("observe_visa_oracle_retirement_age_notice: retirement age notice holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
