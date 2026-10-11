#!/usr/bin/env python3
"""observe_visa_oracle_retirement_no_sponsor.py — bites: observation for R3.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle retirement interview. The retirement
branch no longer asks "who sponsors your stay" because no rule covering
RETIREMENT in the newest signed pack reads sponsor.type. The observation runs
the fact-mapper test file from `apps/mouth`, which holds the pack-scan guard
("sponsor.type x RETIREMENT") that fails if any such rule ever appears, and
requires every test in it to pass. Exit 0 only if Vitest reports the file
passed with zero failures and the guard block is still present in the file.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.test.ts"
GUARD_TITLE = "sponsor.type x RETIREMENT"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MIN_TESTS = 190
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 190.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= MIN_TESTS


def guard_present() -> bool:
    """The pack-scan guard block must still exist in the test file."""
    text = (MOUTH_DIR / TEST_FILE).read_text(encoding="utf-8")
    return GUARD_TITLE in text


def main() -> int:
    if not guard_present():
        print("observe_visa_oracle_retirement_no_sponsor: FAILED (guard block missing)")
        return 1
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
        print(
            f"observe_visa_oracle_retirement_no_sponsor: FAILED ({summary})\n{out[-1500:]}"
        )
        return result.returncode or 1
    print(f"observe_visa_oracle_retirement_no_sponsor: {summary}")
    print("observe_visa_oracle_retirement_no_sponsor: retirement never asks sponsor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
