#!/usr/bin/env python3
"""observe_book_sponsor_line_1014.py — bites: observation for the /book E33F sponsor line.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The observation runs apps/mouth/src/components/book/book-sponsor-line.test.ts with vitest, which
proves: a highlight that is not verbatim in the catalogue row (or is blank) makes the builder
throw at module load; the E33F service's first feature is exactly the sponsor sentence while its
tagline stays the untouched catalogue description_en; the remaining E33F features keep their
order; every other pricing-backed visa service has exactly the features computed from its
snapshot row. It does NOT assert the rendered visibility of the sentence at 320px and 1280px;
that is apps/mouth/e2e/book-pricing.spec.ts, run on Pro (never Playwright on M5).
Exit 0 only on a full pass of at least 6 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/components/book/book-sponsor-line.test.ts"
MIN_TESTS = 6
TIMEOUT_SECONDS = 300

_SUMMARY = re.compile(r"^Tests\s+(\d+) passed \((\d+)\)$")


def summary_ok(line: str | None) -> bool:
    """True only for a vitest line that is a pure pass (no failed/skipped), N >= 6."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS and match.group(1) == match.group(2)


def main() -> int:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "NO_COLOR": "1",
        "CI": "1",
    }
    try:
        result = subprocess.run(
            ["npx", "--no-install", "vitest", "run", TEST_FILE],
            cwd=MOUTH_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"observe_book_sponsor_line_1014: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if ln.strip().startswith("Tests ")]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no vitest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_book_sponsor_line_1014: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_book_sponsor_line_1014: {summary}")
    print("observe_book_sponsor_line_1014: the E33F sponsor sentence is bound to the catalogue row and leads the card features")
    return 0


if __name__ == "__main__":
    sys.exit(main())
