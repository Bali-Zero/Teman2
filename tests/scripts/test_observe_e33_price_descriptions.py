"""Unit tests for the summary parser in scripts/ci/observe_e33_price_descriptions.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_e33_price_descriptions import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "12 skipped in 0.1s",
        "11 passed in 0.1s",
        "1 failed, 11 passed in 0.1s",
        "12 passed, 1 skipped in 0.1s",
        "12 passed, 1 error in 0.1s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize("line", ["12 passed in 0.02s", "13 passed in 1.20s", "==== 12 passed in 0.02s ===="])
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
