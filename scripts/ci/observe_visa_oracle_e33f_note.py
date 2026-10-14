#!/usr/bin/env python3
"""observe_visa_oracle_e33f_note.py — bites: observation for the E33F-only "what the 5-year E33E also needs" note.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs the
engine-adapter, OutcomeSheet, client-copy and E33E/E33F pack-scan test files
from `apps/mouth` and requires every test in them to pass, and each PR-10 test
title to be reported as run: a retirement result with E33F but not E33E carries a
candidate-scoped note on the E33F card (never in the global conditions) saying
what the 5-year E33E would also need, in English and Bahasa Indonesia, and no
note appears when E33E is also a candidate, when E33F is absent, or on dead ends.
It also runs the pack-scan guard pinning that the newest signed pack separates
E33E from E33F only by the deposit trio on retirement eligibility and matches
the note's threshold and conditions.
Exit 0 only if Vitest reports each file passed with zero failures.
"""

# bites-observable — no arguments; one literal program, literal test files.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
BASE = "src/app/(visa-oracle)/visa-oracle"
TEST_FILES = (
    f"{BASE}/_lib/engine-adapter.test.ts",
    f"{BASE}/_components/OutcomeSheet.test.tsx",
    f"{BASE}/_lib/client-copy.test.ts",
    f"{BASE}/_lib/e33e-e33f-pack-scan.test.ts",
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MIN_TESTS = 389
# Titles that prove this change; each must be reported as run, so deleting one
# cannot hide behind the file total staying above MIN_TESTS.
REQUIRED_TESTS = (
    "quotes the localized bank_deposit option label from i18n in EN and ID",
    "undecided -> family_sponsor walk carries the note",
    "names state bank = no, own name = no, and their combination on deposit bases",
    "explains each 'unsure' deposit answer as a conservative count",
    "innocence: emits no note when E33E is also a candidate (E33E + E33F)",
    "innocence: emits no note when E33F is absent",
    "EN/ID parity: every produced note is non-empty in both locales",
    "inside the E33F candidate card (never in .oracle-outcome__conditions)",
    "attributes retirement_basis in demonstratedReviewCauses only when depositBasisDecisivelyNotChosen holds",
    "does not render the E33F_E33E_DEPOSIT_NOTE sentence when E33E+E33F are both supported",
    "carry no engine jargon or promise words",
    "innocence: the newest signed pack has no problems (E33E-only rules are the four named, each twin identical)",
    "the E33E-only rules are exactly the hard filters with identical twins plus el.e33e.retirement and the disputed-band rule",
    "el.e33e.retirement is the E33F rule plus age 55 or more plus the deposit trio",
    "the disputed-band rule never excludes and itself requires the deposit trio",
    "no rule targets both E33E and E33F",
    "the note's EN and ID figures equal the pack's deposit threshold",
    "the note names the state-owned bank and the own-name condition in EN and ID",
    "a harmless new identical twin pair does not fail the scan",
    "guilt: a changed deposit threshold fails the scan",
    "guilt: removing the deposit clause from el.e33e.retirement fails the scan",
    "guilt: appending an age cap to el.e33e.retirement fails the scan",
    "guilt: appending a second deposit leaf to el.e33e.retirement fails the scan",
    "guilt: appending a contradictory state-bank leaf to el.e33e.retirement fails the scan",
    "guilt: a new E33E-only EXCLUDE rule fails the scan",
    "guilt: a new E33F-only SUPPORT rule fails the scan",
    "guilt: adding or removing a global rule fails the scan",
    "guilt: a twin whose on_unknown differs fails the scan",
    "guilt: el.e33e.retirement no longer covering RETIREMENT fails the scan",
    "guilt: el.e33e.retirement with a closed validity period fails the scan",
    "guilt: turning the disputed-band rule into an EXCLUDE fails the scan",
    "guilt: a rule that targets both products fails the scan",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in required if not any(t in l for l in passed)]


def summary_ok(line: str | None, minimum: int = MIN_TESTS) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= minimum."""
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= minimum


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
        print(f"observe_visa_oracle_e33f_note: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_e33f_note: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_e33f_note: {summary}")
    print("observe_visa_oracle_e33f_note: e33f note holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
