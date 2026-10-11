#!/usr/bin/env python3
"""observe_visa_oracle_no_door_copy.py — bites: observation for the no-door dead-end copy.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs the
no-door test file from `apps/mouth` and requires every test in it to pass: a
NO_SUPPORTED_PATH with zero alternatives renders the no-door headline,
sub-headline, share text and two-step list in EN and ID, without the
"open door" step, while a dead end with one door keeps the original copy.
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
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_components/NoPathWithoutDoors.test.tsx"
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
        print(f"observe_visa_oracle_no_door_copy: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_no_door_copy: Tests {summary}")
    print("observe_visa_oracle_no_door_copy: no-door copy holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
