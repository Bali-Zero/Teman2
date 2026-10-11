"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_retirement_reasons.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_retirement_reasons import (  # noqa: E402
    REQUIRED_TESTS,
    missing_tests,
    summary_ok,
)


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
    "line", ["      Tests  100 passed (100)", "      Tests  150 passed (150)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_missing_tests_names_a_deleted_required_test():
    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]


def test_required_titles_are_substrings_of_real_test_titles():
    src = (
        Path(__file__).parent.parent.parent
        / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
    ).read_text()
    for title in REQUIRED_TESTS:
        assert title in src
