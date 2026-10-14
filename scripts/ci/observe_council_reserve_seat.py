#!/usr/bin/env python3
"""observe_council_reserve_seat.py — bites: observation for the council reserve seat.

# bites-observable — this script takes NO arguments: the interpreter, the working directory,
# the test file and the selector are literal strings below, so nothing an invoker types can
# name a program to run, a file to write, or a database to reach.

The consumer is the evidence lint on every gear-3 PR. The observation runs the tests that pin
the reserve bench: agy-gemini-4-argon-high counts toward quorum only with a substitution note,
and the retired agy-gemini-3.1-pro no longer counts. Exit 0 only for a full pass of at least
MIN_TESTS tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "scripts/tests/test_evidence_pack_lint.py"
SELECTOR = "gemini4_argon_high or retired_gemini_3_1_pro or reserve"
MIN_TESTS = 3
_SUMMARY = re.compile(r"^=*\s*(\d+) passed(?:, \d+ deselected)?(?: in [\d.]+s)?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line with N passed, N >= MIN_TESTS, and nothing else
    (no failed, skipped, error, xfail or warnings token)."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-k", SELECTOR, "-p", "no:cacheprovider", "-q"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or " error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_council_reserve_seat: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_council_reserve_seat: {summary}")
    print("observe_council_reserve_seat: council reserve seat holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
