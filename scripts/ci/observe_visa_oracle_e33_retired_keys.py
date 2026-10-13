#!/usr/bin/env python3
"""observe_visa_oracle_e33_retired_keys.py — bites: observation for the retired E33 reason-copy keys.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The consumer is the engine-adapter test suite in the required mouth CI leg. The
observation runs that test file from `apps/mouth`, requires every test to pass,
and requires the two retirement tests to be reported as run: no signed pack at
seq 28 or later emits a retired key, and every E33 advisor-check key in the copy
table is emitted by the highest signed pack or listed as retired.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MIN_TESTS = 100
REQUIRED_TESTS = (
    "retired E33 advisor-check keys: none is emitted by a signed pack at seq >= 28",
    "every E33 advisor-check key in the copy table is emitted by the highest signed pack or listed as retired",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None, minimum: int = MIN_TESTS) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= minimum."""
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= minimum


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in required if not any(t in l for l in passed)]


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=verbose", TEST_FILE],
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
        print(f"observe_visa_oracle_e33_retired_keys: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_e33_retired_keys: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_e33_retired_keys: adapter {summary}")
    print("observe_visa_oracle_e33_retired_keys: e33 retired keys hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
