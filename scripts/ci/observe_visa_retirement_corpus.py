#!/usr/bin/env python3
"""observe_visa_retirement_corpus.py — bites: observation for the retirement walk corpus.

# bites-observable — this script takes NO arguments: the program it runs, the test
# file it names and the file it reads are literal strings in this file, so nothing
# an invoker types can name a program to run, a file to write, or a database to
# reach (the bar `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the required CI census leg. The observation (1) reads the census
pin table and requires EXACTLY 13 age-64 retirement walks split 10
SUPPORTED_CANDIDATES (4 of them [E33E, E33F], 6 [E33F] only; see EXPECTED_* below) and 3
NO_SUPPORTED_PATH (the RETIREMENT_INCOME_BELOW_THRESHOLD dead ends), then (2) runs
the census tests that replay those pins on every pinned sequence and requires a
full pass with no skip. Fewer or more walks, or a different split, fails loud.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
TEST_FILE = "backend/tests/services/visa_engine/test_interview_walk_census.py"
EXPECTED_WALKS = 13
EXPECTED_SUPPORTED = 10
EXPECTED_NO_PATH = 3
EXPECTED_E33E_AND_E33F = 4
EXPECTED_E33F_ONLY = 6
MIN_TESTS = 15
_ROW = re.compile(
    r'^\s*"offshore/retirement/[^"]+/age64/[^"]+":\s*(_E33E_AND_E33F|_E33F_ONLY|_INCOME_BELOW_FLOOR),\s*$'
)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_SUMMARY = re.compile(
    r"^(?:=+ )?(\d+) passed(?:, \d+ deselected)?(?: in [\d.]+s(?: \([^)]*\))?)?(?: =+)?$"
)


def count_rows(text: str) -> dict[str, int]:
    """Tally the retirement pin rows of the census file by outcome constant."""
    tally = {"_E33E_AND_E33F": 0, "_E33F_ONLY": 0, "_INCOME_BELOW_FLOOR": 0}
    for line in text.splitlines():
        match = _ROW.match(line)
        if match:
            tally[match.group(1)] += 1
    return tally


def pins_ok(tally: dict[str, int]) -> bool:
    """True only for exactly 13 walks: 4 + 6 = 10 SUPPORTED_CANDIDATES and 3 NO_SUPPORTED_PATH."""
    supported = tally["_E33E_AND_E33F"] + tally["_E33F_ONLY"]
    return (
        supported == EXPECTED_SUPPORTED
        and tally["_INCOME_BELOW_FLOOR"] == EXPECTED_NO_PATH
        and tally["_E33E_AND_E33F"] == EXPECTED_E33E_AND_E33F
        and tally["_E33F_ONLY"] == EXPECTED_E33F_ONLY
        and supported + tally["_INCOME_BELOW_FLOOR"] == EXPECTED_WALKS
    )


def summary_ok(line: str | None) -> bool:
    """True only for a pytest summary of the form `N passed` (optionally with the
    duration), N >= MIN_TESTS. Any failed, skipped, error or xfail text is False."""
    if line is None:
        return False
    match = _SUMMARY.match(_ANSI.sub("", line).strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    text = (BACKEND_RAG_DIR / TEST_FILE).read_text(encoding="utf-8")
    tally = count_rows(text)
    supported = tally["_E33E_AND_E33F"] + tally["_E33F_ONLY"]
    walks = supported + tally["_INCOME_BELOW_FLOOR"]
    print(
        f"observe_visa_retirement_corpus: retirement walks={walks} "
        f"SUPPORTED_CANDIDATES={supported} NO_SUPPORTED_PATH={tally['_INCOME_BELOW_FLOOR']}"
    )
    if not pins_ok(tally):
        print(
            "observe_visa_retirement_corpus: FAILED (pin table is not 13 walks split 10 / 3)"
        )
        return 1
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            TEST_FILE,
            "-k",
            "replay_to_their_pins or expected_real or name_their_cause or (ends_in_its_pinned and not candidate_pack)",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_RAG_DIR,
        env={**os.environ, "PYTHONPATH": "."},
        check=False,
        capture_output=True,
        text=True,
    )
    out = _ANSI.sub("", result.stdout + result.stderr)
    lines = [ln for ln in out.splitlines() if " passed" in ln]
    line = lines[-1] if lines else None
    if result.returncode != 0 or not summary_ok(line):
        print(
            f"observe_visa_retirement_corpus: FAILED ({line})\n{result.stdout[-1500:]}"
        )
        return result.returncode or 1
    print(f"observe_visa_retirement_corpus: {line.strip()}")
    print(
        "observe_visa_retirement_corpus: 13 retirement walks, 10 SUPPORTED_CANDIDATES "
        "and 3 NO_SUPPORTED_PATH, replayed green"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
