#!/usr/bin/env python3
"""observe_visa_oracle_no_door_replay_freshness.py — bites: observation for the no-door dead-end copy.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the required mouth CI leg on every signed-pack PR. The observation
runs the freshness test file from `apps/mouth` and requires every test in it to
pass: the no-door replay fixture is recorded on the numerically highest
`rulepack-prod-NNN.signed.json`, an older recording is reported stale, and a newer
pack landing makes the current recording stale.
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
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/no-path-doors-fixture-freshness.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


MIN_TESTS = 4
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 4.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= MIN_TESTS


def last_summary_line(out: str) -> str | None:
    """The LAST line beginning with `Tests`: Vitest prints its real summary at the end,
    so an earlier test-logged line cannot spoof it."""
    found = re.findall(r"^\s*Tests\s.*$", out, re.MULTILINE)
    return found[-1] if found else None


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", TEST_FILE],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    line = last_summary_line(out)
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_visa_oracle_no_door_replay_freshness: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_oracle_no_door_replay_freshness: {summary}")
    print("observe_visa_oracle_no_door_replay_freshness: no-door replay is fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
