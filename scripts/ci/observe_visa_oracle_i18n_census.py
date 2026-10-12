#!/usr/bin/env python3
"""observe_visa_oracle_i18n_census.py — bites: observation for the i18n dead-key census.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the mouth Vitest run. The observation runs the census test file
from `apps/mouth` and requires every test in it to pass: no unreferenced key
outside the frozen allowlist, no allowlisted key that is now referenced or gone,
EN/ID parity, and none of the 46 keys #8205 deleted back in the dictionary.
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
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/i18n-census.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", TEST_FILE],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"Tests\s+(.+?)\s*$", out, re.MULTILINE)
    summary = tests.group(1) if tests else "no Vitest summary"
    if result.returncode != 0 or "failed" in summary or tests is None:
        print(f"observe_visa_oracle_i18n_census: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_i18n_census: Tests {summary}")
    print("observe_visa_oracle_i18n_census: census holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
