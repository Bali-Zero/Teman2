"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_remote_income_question.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_remote_income_question import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  8 skipped (8)",
        "      Tests  8 passed (8)",
        "      Tests  1 failed | 8 passed (9)",
        "      Tests  9 passed | 1 skipped (10)",
        "      Tests  9 passed | 1 todo (10)",
        "      Tests  8 passed (9)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  9 passed (9)", "      Tests  10 passed (10)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
