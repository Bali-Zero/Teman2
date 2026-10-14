#!/usr/bin/env python3
"""observe_visa_oracle_i18n_qualifying.py — bites: observation for E33 investment property ID qualifying wording.

# bites-observable — this script takes NO arguments: the program it runs and the
# files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the Visa Oracle i18n dictionary and its parity test suite. Every
English entry that says "qualifying" has an Indonesian twin that says "memenuhi
syarat", and `q.investment_vehicle.opt.property` (ID) reads "Properti yang
memenuhi syarat". Two observations, both required:

1. a literal scan of `i18n.ts`: `"q.investment_vehicle.opt.property": "Properti yang memenuhi syarat",`
   appears exactly once and the retired "Pengaturan properti" line is gone;
2. `i18n.test.ts` passes in full, with the qualifying-parity test reported as run.

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
I18N_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/i18n.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MIN_TESTS = 11
INVEST_ID_LINE = '"q.investment_vehicle.opt.property": "Properti yang memenuhi syarat",'
OLD_INVEST_ID_LINE = '"q.investment_vehicle.opt.property": "Pengaturan properti",'
REJECTED_HYBRID = "Pengaturan properti yang memenuhi syarat"

REQUIRED_TESTS = (
    "every English string that says 'qualifying' has an Indonesian twin that says 'memenuhi syarat'",
    "pins q.investment_vehicle.opt.property in both languages and keeps the ID label figure-free",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= MIN_TESTS."""
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


def source_problems(source: str) -> list[str]:
    """Literal source scan of i18n.ts for the qualifying property wording."""
    lines = [
        l for l in source.splitlines() if not l.lstrip().startswith("//")
    ]
    problems: list[str] = []

    invest_hits = [l for l in lines if INVEST_ID_LINE in l]
    if len(invest_hits) != 1:
        problems.append(f"{INVEST_ID_LINE}: {len(invest_hits)} lines (expected 1)")

    if any(OLD_INVEST_ID_LINE in l for l in lines):
        problems.append(f"retired line still present: {OLD_INVEST_ID_LINE}")

    if any(REJECTED_HYBRID in l for l in lines):
        problems.append(f"rejected hybrid wording present: {REJECTED_HYBRID!r}")

    return problems


def main() -> int:
    source = (MOUTH_DIR / I18N_FILE).read_text(encoding="utf-8")
    problems = source_problems(source)
    if problems:
        print(
            "observe_visa_oracle_i18n_qualifying: FAILED "
            f"(source problems: {problems})"
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
        print(f"observe_visa_oracle_i18n_qualifying: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(
            "observe_visa_oracle_i18n_qualifying: FAILED "
            f"(required tests absent: {absent})"
        )
        return 1
    print(f"observe_visa_oracle_i18n_qualifying: {summary}")
    print("observe_visa_oracle_i18n_qualifying: i18n qualifying holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
