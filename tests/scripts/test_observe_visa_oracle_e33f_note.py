"""Unit tests for the parsers in scripts/ci/observe_visa_oracle_e33f_note.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_e33f_note import (  # noqa: E402
    MIN_TESTS,
    REQUIRED_TESTS,
    missing_tests,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        f"      Tests  {MIN_TESTS} skipped ({MIN_TESTS})",
        f"      Tests  {MIN_TESTS - 1} passed ({MIN_TESTS - 1})",
        f"      Tests  1 failed | {MIN_TESTS} passed ({MIN_TESTS + 1})",
        f"      Tests  {MIN_TESTS} passed | 1 skipped ({MIN_TESTS + 1})",
        f"      Tests  {MIN_TESTS} passed | 1 todo ({MIN_TESTS + 1})",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


def test_accepts_full_pass_at_or_above_floor():
    assert summary_ok(f"      Tests  {MIN_TESTS} passed ({MIN_TESTS})") is True
    assert summary_ok(f"      Tests  {MIN_TESTS + 5} passed ({MIN_TESTS + 5})") is True


def test_missing_tests_names_a_deleted_required_test():
    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]
