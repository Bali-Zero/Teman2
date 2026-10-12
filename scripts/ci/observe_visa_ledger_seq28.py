#!/usr/bin/env python3
"""observe_visa_ledger_seq28.py — bites: observation for the seq-28 corner-skill ledger.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is every session that loads /visaoracle. The observation runs the
ledger test file and requires every test in it to pass: SKILL.md and the
live-state log carry the seq-28 activation, the two seq-28 PENDING-ARMS rows are
closed with proof, the seq-29 freshness row appears exactly once, and no
PENDING-ARMS line is duplicated.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "tests/scripts/test_visa_ledger_seq28.py"
MIN_TESTS = 6
_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [0-9.]+s(?: \([0-9:]+\))?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is exactly `N passed in Xs`, N >= 6.

    Anything else (failed, skipped, error, xfail, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if re.search(r"\bin [0-9.]+s", ln)]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_visa_ledger_seq28: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_ledger_seq28: {summary}")
    print("observe_visa_ledger_seq28: seq-28 ledger holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
