"""Unit tests for the parser in scripts/ci/observe_visa_oracle_replay_pins.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_replay_pins import REQUIRED_TESTS, missing_tests, summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  150 skipped (150)",
        "      Tests  149 passed (149)",
        "      Tests  1 failed | 150 passed (151)",
        "      Tests  150 passed | 1 todo (151)",
        "      Tests  150 passed (151)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


def test_accepts_full_pass_at_or_above_floor():
    assert summary_ok("      Tests  150 passed (150)") is True


def test_missing_tests_names_a_deleted_required_test():
    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]
