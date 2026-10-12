"""Unit tests for the summary parser in scripts/ci/observe_visa_engine_annual_income_fact.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_engine_annual_income_fact import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "========== 7 passed in 0.02s ==========",
        "========== 7 skipped in 0.02s ==========",
        "========== 6 passed in 0.02s ==========",
        "========== 5 passed in 0.02s ==========",
        "========== 1 failed, 7 passed in 0.02s ==========",
        "========== 7 passed, 1 skipped in 0.02s ==========",
        "========== 7 passed, 1 error in 0.02s ==========",
        "========== 7 passed, 1 xfailed in 0.02s ==========",
        "========== 7 passed, 2 deselected in 0.02s ==========",
        "7 passed, 1 skipped in 0.02s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    [
        "========== 8 passed in 0.02s ==========",
        "========== 8 passed in 1.20s (0:00:01) ==========",
        "========== 8 passed, 1 warning in 0.02s ==========",
        "8 passed in 0.04s",
    ],
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
