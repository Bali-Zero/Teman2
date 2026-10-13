#!/usr/bin/env python3
"""observe_visa_oracle_e33_income_wording.py — bites: observation for the E33 income wording.

# bites-observable — this script takes NO arguments: the program it runs and the
# files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The E33-family result sentences
say "income or allowance" (EN) and "penghasilan atau tunjangan" (ID), as the official
page and the interview do. Two observations, both required:

1. a literal scan of the engine adapter source: no visible copy line carries "passive
   income" or "penghasilan pasif" (comment lines are not copy and are skipped);
2. the engine-adapter test file passes in full, with the tests that pin the retirement
   income sentences reported as run.

Exit 0 only if both hold.
"""

# bites-observable — no arguments; one literal program, literal files.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
ADAPTER = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MIN_TESTS = 100
BANNED = re.compile(r"passive[ -]income|penghasilan pasif", re.IGNORECASE)
REQUIRED_COPY = ("income or allowance", "penghasilan atau tunjangan")
REQUIRED_TESTS = (
    "echoes a declared 2,999 and names the USD 3,000 minimum, EN and ID",
    "says a 'not sure' counted as zero instead of claiming a figure was given",
    "falls back to the neutral static sentence",
    "keeps the retirement sentence when unrelated Second Home and paid-activity facts are also populated",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= 100."""
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= MIN_TESTS


def missing_tests(out: str) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in REQUIRED_TESTS if not any(t in l for l in passed)]


def banned_lines(source: str) -> list[int]:
    """1-based numbers of non-comment lines carrying a banned phrase."""
    hits = []
    for number, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith("//"):
            continue
        if BANNED.search(line):
            hits.append(number)
    return hits


def copy_present(source: str) -> list[str]:
    """Required phrases absent from the source."""
    return [p for p in REQUIRED_COPY if p not in source]


def main() -> int:
    source = (MOUTH_DIR / ADAPTER).read_text(encoding="utf-8")
    hits = banned_lines(source)
    absent_copy = copy_present(source)
    if hits or absent_copy:
        print(
            "observe_visa_oracle_e33_income_wording: FAILED "
            f"(banned lines {hits}, absent phrases {absent_copy})"
        )
        return 1
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
        print(f"observe_visa_oracle_e33_income_wording: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_e33_income_wording: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_e33_income_wording: {summary}")
    print("observe_visa_oracle_e33_income_wording: income wording holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
