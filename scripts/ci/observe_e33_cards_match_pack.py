#!/usr/bin/env python3
"""observe_e33_cards_match_pack.py — bites: observation for the E33-family doctrine cards.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The consumer is the next doctrine or visa session that reads the seven E33 cards and the E33
fact registry. The observation runs the pytest file that diffs each card against the active signed
pack and requires a full pass of at least 23 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "tests/scripts/test_e33_cards_match_pack.py"
MIN_TESTS = 23
TIMEOUT_SECONDS = 240
_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= 18."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST_FILE],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"observe_e33_cards_match_pack: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_e33_cards_match_pack: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_e33_cards_match_pack: {summary}")
    print("observe_e33_cards_match_pack: cards match the pack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
