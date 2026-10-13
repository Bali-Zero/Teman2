"""Unit tests for the summary parser in scripts/ci/observe_e33_cards_match_pack.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_e33_cards_match_pack import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "18 skipped in 0.1s",
        "17 passed in 0.1s",
        "1 failed, 17 passed in 0.1s",
        "18 passed, 1 skipped in 0.1s",
        "18 passed, 1 error in 0.1s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize("line", ["18 passed in 0.02s", "19 passed in 1.20s", "==== 18 passed in 0.02s ===="])
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
