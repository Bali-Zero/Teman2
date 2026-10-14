#!/usr/bin/env python3
"""observe_visa_oracle_e33_income_wording.py — bites: observation for the E33 income wording.

# bites-observable — this script takes NO arguments: the program it runs and the
# files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the adapter contract that builds the public result sentences (source
plus its unit tests; the live page is observed after deploy, outside CI). The E33-family result sentences
say "income or allowance" (EN) and "penghasilan atau tunjangan" (ID), as the official
page and the interview do. Two observations, both required:

1. a literal scan of the engine adapter source: no visible copy line carries "passive
   income", "penghasilan pasif" or the hyphenated "income-or-allowance", and each of
   the E33-family sentences (EN and ID, every dynamic branch) carries its wording on
   its own line (comment lines are not copy and are skipped);
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
BANNED = re.compile(
    r"passive[ -]income|penghasilan pasif|income-or-allowance|penghasilan-atau-tunjangan",
    re.IGNORECASE,
)
EN_PHRASE = "income or allowance"
ID_PHRASE = "penghasilan atau tunjangan"
REQUIRED_COPY = (EN_PHRASE, ID_PHRASE)
# One row per E33-family result sentence: a literal anchor that identifies exactly one
# copy line, and the wording that line must carry. Each sentence is checked on its own,
# so a third wording on one sentence cannot hide behind the others.
SENTENCES = (
    ("plus income or allowance of ${usd(RETIREMENT_INCOME_THRESHOLD_USD, \"en-US\")}", EN_PHRASE),
    ("ditambah penghasilan atau tunjangan minimal", ID_PHRASE),
    ('"Retirement with income or allowance of USD 3,000', EN_PHRASE),
    ('"Pensiun dengan penghasilan atau tunjangan minimal USD 3.000', ID_PHRASE),
    ('"This route can be met on a deposit basis or an', EN_PHRASE),
    ('"Jalur ini dapat dipenuhi berbasis deposito', ID_PHRASE),
    ("plus monthly income or allowance; for a visit", EN_PHRASE),
    ("ditambah penghasilan atau tunjangan bulanan; untuk kunjungan", ID_PHRASE),
    ("`The retirement visas (E33E/E33F) need documented", EN_PHRASE),
    ("`Visa pensiun (E33E/E33F) memerlukan", ID_PHRASE),
    ("`You were not sure of your monthly", EN_PHRASE),
    ("`Anda belum yakin dengan", ID_PHRASE),
    ("`You declared ${usd(value", EN_PHRASE),
    ("`Anda menyatakan ${usd(value", ID_PHRASE),
)
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


def sentence_problems(source: str) -> list[str]:
    """Anchors that match no line, more than one line, or a line without its wording."""
    lines = source.splitlines()
    problems = []
    for anchor, phrase in SENTENCES:
        found = [l for l in lines if anchor in l and not l.lstrip().startswith("//")]
        if len(found) != 1:
            problems.append(f"{anchor!r}: {len(found)} lines")
        elif phrase not in found[0]:
            problems.append(f"{anchor!r}: lacks {phrase!r}")
    return problems


def main() -> int:
    source = (MOUTH_DIR / ADAPTER).read_text(encoding="utf-8")
    hits = banned_lines(source)
    absent_copy = copy_present(source) + sentence_problems(source)
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
