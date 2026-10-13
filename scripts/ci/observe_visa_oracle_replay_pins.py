#!/usr/bin/env python3
"""observe_visa_oracle_replay_pins.py — bites: observation for the no-door replay and E33G copy pins.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page under the active signed pack.
The observation runs the no-path-doors replay test and the engine-adapter test
from `apps/mouth` and requires every test to pass, and the walks that carry the
E33G income-threshold sentence (remote persona at foreign income 59,999) to be
reported as run. Exit 0 only on a full pass.
"""

# bites-observable — no arguments; one literal program, two literal test files.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
LIB = "src/app/(visa-oracle)/visa-oracle/_lib/"
TEST_FILES = (LIB + "no-path-doors.test.tsx", LIB + "engine-adapter.test.ts")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MIN_TESTS = 150
REQUIRED_TESTS = (
    "covers the 17 dead ends, 3 held walks and 1 missing-input walk the current census reports",
    "names a door the pack actually supports: offshore/remote/foreign_only/income_59999",
    "states every cause in words, EN and ID: offshore/remote/foreign_only/income_59999",
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
        ["npx", "vitest", "run", "--reporter=verbose", *TEST_FILES],
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
        print(f"observe_visa_oracle_replay_pins: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_replay_pins: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_replay_pins: {summary}")
    print("observe_visa_oracle_replay_pins: replay pins hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
