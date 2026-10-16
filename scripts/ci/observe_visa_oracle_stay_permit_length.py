#!/usr/bin/env python3
"""observe_visa_oracle_stay_permit_length.py — bites: observation for the stay-permit length on priced results.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs four
Vitest files from `apps/mouth` and requires every test in each to pass:

* engine-response.test.ts — the runtime guard reads `stay_policy` on every display
  candidate, requires it, tolerates unknown extra keys, and rejects malformed shapes;
* engine-adapter.test.ts — a permit length (1-year / 5-year) appears only beside the
  candidate's own AVAILABLE price, the renewal line only for a VERIFIED and allowed
  extension, the longer-stay sentence only inside the pack's renewal coverage, and the
  signed-pack E28A (730) renders its 2-year length and the longer-stay renewal line (page: extendable); E30A, BRIDGING and A1
  render no length, renewal or raw code;
* OutcomeSheet.duration.test.tsx — E28A's fixed 730-day stay renders the 2-year permit, and the
  longer-stay renewal line for a 1000-day plan, EN and ID;
* OutcomeSheet.test.tsx — the sheet and the share summary carry the same wording, EN and ID.

Exit 0 only if Vitest reports each file passed with zero failures and every required
test title was reported as run.
"""

# bites-observable — no arguments; one literal program, literal test files.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
LIB = "src/app/(visa-oracle)/visa-oracle/_lib/"
COMPONENTS = "src/app/(visa-oracle)/visa-oracle/_components/"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")

# (file, minimum tests in the file, titles that must be reported as run). A deleted
# required test cannot hide behind the file total staying above the minimum.
FILES = (
    (
        LIB + "engine-response.test.ts",
        1,
        (
            "parses valid stay_policy shapes and optional nulls",
            "accepts unknown extra keys on stay_policy, stay, and extension",
            "rejects a display candidate with an absent stay_policy",
            "rejects malformed stay_policy shapes",
        ),
    ),
    (
        LIB + "engine-adapter.test.ts",
        228,
        (
            "within 2190-day coverage, and advisor line above 2190",
            "for priced Working KITAS (E23)",
            "shows 5-year length for E33 and E33E with no extension sentence",
            "omits permit length for unquoted candidates (E33A, E33B, E33C)",
            "keeps E31 duration-option candidates unchanged",
            "guilt: signed-pack E28A (730 + 100x365) shows its 2-year length and the continue-by-renewal line, because the page states the permit is extendable; E30A (365/730 UNKNOWN), BRIDGING (FIXED_DAYS null/60), and A1",
            "maintains non-empty distinct EN/ID parity across all PR-7 stay-permit copy tables",
        ),
    ),
    (
        COMPONENTS + "OutcomeSheet.duration.test.tsx",
        1,
        (
            "EN: '2-year stay permit', and a 1000-day plan shows the continue-by-renewal line",
            "ID: 'Izin tinggal 2 tahun', and a 1000-day plan shows the continue-by-renewal line",
        ),
    ),
    (
        COMPONENTS + "OutcomeSheet.test.tsx",
        1,
        (
            "renders E33F 1-year permit length, verified renewal line, and longer-stay renewal note",
            "renders E33 5-year permit length with no renewal sentence",
        ),
    ),
)


def summary_ok(line: str | None, minimum: int = 1) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= minimum.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= minimum


def missing_tests(out: str, required: tuple[str, ...]) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in required if not any(t in l for l in passed)]


def run_vitest(test_file: str, minimum: int, required: tuple[str, ...]) -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=verbose", test_file],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"^\s*Tests\s.*$", out, re.MULTILINE)
    line = tests.group(0) if tests else None
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line, minimum):
        print(f"observe_visa_oracle_stay_permit_length: FAILED {test_file} ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out, required)
    if absent:
        print(f"observe_visa_oracle_stay_permit_length: FAILED {test_file} (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_stay_permit_length: {test_file} {summary}")
    return 0


def main() -> int:
    for test_file, minimum, required in FILES:
        code = run_vitest(test_file, minimum, required)
        if code:
            return code
    print("observe_visa_oracle_stay_permit_length: stay-permit length holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
