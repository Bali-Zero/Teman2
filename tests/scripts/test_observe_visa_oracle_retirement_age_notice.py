"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_retirement_age_notice.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_retirement_age_notice import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  5 skipped (5)",
        "      Tests  4 passed (4)",
        "      Tests  1 failed | 4 passed (5)",
        "      Tests  5 passed | 1 skipped (6)",
        "      Tests  5 passed | 1 todo (6)",
        "      Tests  4 passed (5)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  5 passed (5)", "      Tests  6 passed (6)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
