"""Unit tests for the summary parser in scripts/ci/observe_brochure_price_parity.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_brochure_price_parity import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "15 skipped in 0.1s",
        "14 passed in 0.1s",
        "1 failed, 15 passed in 0.1s",
        "15 passed, 1 skipped in 0.1s",
        "15 passed, 1 error in 0.1s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    ["15 passed in 0.02s", "16 passed in 1.20s", "==== 15 passed in 0.02s ====", "\x1b[32m15 passed\x1b[0m in 4.27s"],
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
