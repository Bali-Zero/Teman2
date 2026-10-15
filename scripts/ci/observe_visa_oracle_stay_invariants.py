#!/usr/bin/env python3
"""observe_visa_oracle_stay_invariants.py — bites: observation for the stay-policy census and the stay-kind quarantine.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page under the active signed pack.
The observation runs the stay-policy census (one case per product of the highest-sequence
signed production pack, plus the coverage case), the engine-response guard and the engine-adapter
test from `apps/mouth`, and requires: every test to pass, the census file and the engine-response
file to report their exact counts, and the guilt and innocence titles of the stay-kind quarantine
to be reported as run. Exit 0 only on a full pass.
"""

# bites-observable — no arguments; one literal program, three literal test files.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
LIB = "src/app/(visa-oracle)/visa-oracle/_lib/"
CENSUS = "stay-policy-census.test.ts"
RESPONSE = "engine-response.test.ts"
ADAPTER = "engine-adapter.test.ts"
TEST_FILES = (LIB + CENSUS, LIB + RESPONSE, LIB + ADAPTER)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Exact census of the two files this lane owns: 38 products of pack 029 plus the coverage case,
# and the engine-response guard. A lost test is a red observer, not a quiet drop. When a future
# pack adds a product, the census file grows by one and this number moves in the same commit.
EXPECTED_BY_FILE = {CENSUS: 39, RESPONSE: 20}
REQUIRED_TESTS = (
    "selects the highest-sequence signed pack on disk and covers every product",
    "accepts a stay policy that breaks a stay-kind invariant instead of failing the page",
    "omits duration without failing the page for each of the four stay-kind invariant breaks on a priced E33F candidate",
    "omits duration without failing the page for each of the four stay-kind invariant breaks even when selected_duration_days and duration_options are valid",
    "preserves E31 duration options when stay is FIXED_DAYS 365/730",
    "a candidate with a broken stay-kind invariant does not remove the permit-length line of a valid sibling",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line `Tests  N passed (N)` with at least one test and nothing failed or skipped."""
    if line is None:
        return False
    match = _SUMMARY.match(line)
    return (
        match is not None
        and match.group(1) == match.group(2)
        and int(match.group(1)) > 0
    )


def passed_per_file(out: str) -> dict[str, int]:
    """Checkmark lines of the verbose reporter, counted for each census-pinned file."""
    lines = [row for row in out.splitlines() if "✓" in row or "✔" in row]
    return {name: sum(1 for row in lines if name in row) for name in EXPECTED_BY_FILE}


def census_drift(
    counts: dict[str, int], expected: dict[str, int] = EXPECTED_BY_FILE
) -> list[str]:
    return [
        f"{name}: {counts.get(name, 0)} passed, expected {want}"
        for name, want in expected.items()
        if counts.get(name, 0) != want
    ]


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [row for row in out.splitlines() if "✓" in row or "✔" in row]
    return [t for t in required if not any(t in row for row in passed)]


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
        print(f"observe_visa_oracle_stay_invariants: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    drift = census_drift(passed_per_file(out))
    if drift:
        print(f"observe_visa_oracle_stay_invariants: FAILED (census drift: {drift})")
        return 1
    absent = missing_tests(out)
    if absent:
        print(
            f"observe_visa_oracle_stay_invariants: FAILED (required tests absent: {absent})"
        )
        return 1
    print(f"observe_visa_oracle_stay_invariants: {summary}")
    print(
        "observe_visa_oracle_stay_invariants: stay-kind quarantine and signed-pack census hold"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
