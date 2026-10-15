#!/usr/bin/env python3
"""observe_catalogue_decisions_1014.py — bites: observation for Zero's 2026-10-14 catalogue decisions.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The observation runs tests/scripts/test_catalogue_decisions_1014.py, which proves: the mouth
price mirror omits the three generic Retirement rows, the backend catalogue keeps them (and its
consumers keep resolving them), the /book retirement card points to the E33F Offshore row at the
same price, every E33F row names the sponsor once at the end, and the sync script skips internal
rows. It does NOT assert the printable price list, the brochure template or the route 404; those
are covered by scripts/pricelist_2026/tests and test_public_pricing_lookup.py respectively.
Exit 0 only on a full pass of at least 17 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "tests/scripts/test_catalogue_decisions_1014.py"
MIN_TESTS = 17
TIMEOUT_SECONDS = 240

_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= 17."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                TEST_FILE,
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"observe_catalogue_decisions_1014: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_catalogue_decisions_1014: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_catalogue_decisions_1014: {summary}")
    print("observe_catalogue_decisions_1014: catalogue decisions of 2026-10-14 hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
