#!/usr/bin/env python3
"""observe_c1_c6_price_descriptions.py — bites: observation for the C1 and C6 price descriptions.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The consumer is the pricing knowledge layer (PricingService.get_all_prices and the public
pricing endpoint), which serves the rows of bali_zero_official_prices_2026.json, and the mouth
mirror that the /book Most popular tagline reads. The observation runs the pytest file that goes
through PricingService.get_all_prices() and requires the C1 and C6 rows to carry the official stay
and visa-validity wording, no business ban, and the selling and pay prohibition, in both files.
Exit 0 only if pytest reports a full pass of at least 12 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "tests/scripts/test_c1_c6_price_descriptions.py"
MIN_TESTS = 12
TIMEOUT_SECONDS = 240
_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= 12."""
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
        print(f"observe_c1_c6_price_descriptions: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_c1_c6_price_descriptions: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_c1_c6_price_descriptions: {summary}")
    print("observe_c1_c6_price_descriptions: C1 C6 descriptions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
