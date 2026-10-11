"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_e33_deposit_reason.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_e33_deposit_reason import missing_tests, summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  100 skipped (100)",
        "      Tests  99 passed (99)",
        "      Tests  1 failed | 99 passed (100)",
        "      Tests  100 passed | 1 skipped (101)",
        "      Tests  100 passed | 1 todo (101)",
        "      Tests  99 passed (100)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  100 passed (100)", "      Tests  101 passed (101)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_missing_tests_names_a_deleted_required_test():
    from observe_visa_oracle_e33_deposit_reason import REQUIRED_TESTS, missing_tests

    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]


def test_summary_ok_honours_a_per_file_minimum():
    assert summary_ok("  Tests  4 passed (4)", 4) is True
    assert summary_ok("  Tests  3 passed (3)", 4) is False
    assert summary_ok("  Tests  4 passed (4)") is False


def test_missing_tests_takes_the_required_list():
    out = "  ✓ a > shows the holder sentence (EN)\n"
    assert missing_tests(out, ("shows the holder sentence (EN)",)) == []
    assert missing_tests(out, ("shows the Indonesian sentence in ID",)) == [
        "shows the Indonesian sentence in ID"
    ]
