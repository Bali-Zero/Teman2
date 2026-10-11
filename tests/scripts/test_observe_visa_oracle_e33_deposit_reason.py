"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_e33_deposit_reason.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_e33_deposit_reason import summary_ok  # noqa: E402


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
