#!/usr/bin/env python3
"""Guilt + innocence suite for the `.husky/pre-commit` Law-2 PII gate's
PII_PASS regex (superscar #3 — guard over-match).

Found 2026-07-12 (PENDING-ARMS): the bare `no\\.?` alternative had no word
boundary, so `passport ... Normalization` false-positived — "No" inside
"Normalization" matched the alternative, and the trailing "rmalization"
(11 alnum chars) satisfied the `{6,}` tail, blocking an innocent commit.

Second round 2026-07-30: word boundaries fixed the "no"-inside-a-word trap but
left the TAIL a bare `[A-Za-z0-9]{6,}`, which happily matched the ordinary
English word that follows the keyword in prose. Measured on the live pattern:
"passport number required", "passport number requirements for KITAS",
"passport no longer accepted", "send us your passport number please" and
"passport number changed in 2025 rules" ALL blocked a commit, while "the
passport number field is mandatory" passed only because "field" happens to be
five letters — a length lottery, not a rule. The same measurement exposed the
UNDER-match twin: a hyphenated "Passport No. C-1234567" was never caught at
all. Cure: the tail must contain a DIGIT (passport numbers do; English words
don't), with an optional leading letter group and separator. Over-match and
under-match on one line — the signature of superscar #3.

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
    # ---- innocence: ordinary prose AFTER a legitimate keyword (2026-07-30) ----
    # Every one of these blocked a real commit under the old digitless tail.
    ("passport number required", False, "INNOCENCE: 'required' is a word, not a number"),
    ("passport number requirements for KITAS", False, "INNOCENCE: same, longer tail"),
    ("passport no longer accepted", False, "INNOCENCE: 'no longer' is English, not 'No.'"),
    ("the passport number field is mandatory", False, "INNOCENCE: passed before only by length luck"),
    ("send us your passport number please", False, "INNOCENCE: instruction to a client, no number"),
    ("passport number changed in 2025 rules", False, "INNOCENCE: a year elsewhere in the sentence"),
    # ---- guilt: real passport-number-shaped strings must still be caught ------
    ("passport no 12345678", True, "GUILT: bare 'no' + digits"),
    ("passport no 123456", True, "GUILT: shortest realistic all-digit form"),
    ("Passport No. C-1234567", True, "GUILT: hyphenated — MISSED by the pre-2026-07-30 pattern"),
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
