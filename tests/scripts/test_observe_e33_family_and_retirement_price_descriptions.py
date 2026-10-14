"""Unit tests for the summary parser in scripts/ci/observe_e33_family_and_retirement_price_descriptions.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_e33_family_and_retirement_price_descriptions import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "56 skipped in 0.1s",
        "55 passed in 0.1s",
        "1 failed, 55 passed in 0.1s",
        "56 passed, 1 skipped in 0.1s",
        "56 passed, 1 error in 0.1s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize("line", ["56 passed in 0.02s", "57 passed in 1.20s", "==== 56 passed in 0.02s ===="])
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
