#!/usr/bin/env python3
"""Guilt + innocence suite for the `.husky/pre-commit` Law-2 PII gate's
PII_PASS regex (superscar #3 — guard over-match).

Found 2026-07-12 (PENDING-ARMS): the bare `no\\.?` alternative had no word
boundary, so `passport ... Normalization` false-positived — "No" inside
"Normalization" matched the alternative, and the trailing "rmalization"
(11 alnum chars) satisfied the `{6,}` tail, blocking an innocent commit.

The pattern is extracted LIVE from .husky/pre-commit (not re-typed here) so
this test breaks the moment the guard drifts from what actually runs, and
exercised via the real `grep -Eiq` the hook shells out to — not a
Python-`re` reimplementation that could silently diverge in semantics.

Run:  python3 scripts/tests/test_husky_pii_pass_overmatch.py
      pytest scripts/tests/test_husky_pii_pass_overmatch.py -q
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK_FILE = REPO_ROOT / ".husky" / "pre-commit"


def _extract_pii_pass_pattern() -> str:
    text = HOOK_FILE.read_text()
    m = re.search(r"^\s*PII_PASS='(.*)'\s*$", text, re.MULTILINE)
    assert m, f"PII_PASS assignment not found in {HOOK_FILE}"
    return m.group(1)


def _matches(pattern: str, line: str) -> bool:
    r = subprocess.run(
        ["grep", "-Eiq", pattern],
        input=line,
        text=True,
        capture_output=True,
    )
    return r.returncode == 0


CASES: list[tuple[str, bool, str]] = [
    # ---- innocence: real prose containing "no"-as-substring, not passport# ----
    ("passport Normalization test", False, "INNOCENCE: 'No' inside 'Normalization' is not passport no."),
    ("the passport normalization step runs first", False, "INNOCENCE: same trap, lowercase"),
    ("passport notes for the intake form", False, "INNOCENCE: 'no' inside 'notes'"),
    ("update the passport nomenclature doc", False, "INNOCENCE: 'no' inside 'nomenclature'"),
    # ---- guilt: real passport-number-shaped strings must still be caught ------
    ("passport no 12345678", True, "GUILT: bare 'no' + digits"),
    ("passport no. AB1234567", True, "GUILT: 'no.' + alnum"),
    ("Passport No: X1234567", True, "GUILT: capitalized 'No:'"),
    ("passport number: A1234567", True, "GUILT: 'number:' + alnum"),
    ("passport #A1234567", True, "GUILT: '#' + alnum"),
    ("passport: A1234567", True, "GUILT: ':' + alnum"),
]


def main() -> int:
    pattern = _extract_pii_pass_pattern()
    failures = []
    for line, should_match, label in CASES:
        got = _matches(pattern, line)
        if got != should_match:
            failures.append(f"  {label}\n    line={line!r} expected_match={should_match} got={got}")
    if failures:
        print("FAIL — PII_PASS guard conformance regression:")
        print("\n".join(failures))
        return 1
    print(f"OK — {len(CASES)}/{len(CASES)} guilt+innocence cases pass ({HOOK_FILE})")
    return 0


def test_pii_pass_guilt_and_innocence():
    pattern = _extract_pii_pass_pattern()
    for line, should_match, label in CASES:
        assert _matches(pattern, line) == should_match, label


if __name__ == "__main__":
    sys.exit(main())
