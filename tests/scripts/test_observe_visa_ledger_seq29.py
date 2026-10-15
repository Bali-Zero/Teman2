"""Unit tests for the summary parser in scripts/ci/observe_visa_ledger_seq29.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_ledger_seq29 import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "8 passed in 0.02s",
        "38 passed in 0.02s",
        "1 failed, 9 passed in 0.03s",
        "9 passed, 1 skipped in 0.03s",
        "9 passed, 1 xfailed in 0.03s",
        "9 passed, 1 warning in 0.03s",
        "9 passed, 1 error in 0.03s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["43 passed in 0.02s", "===== 44 passed in 1.20s =====", "43 passed in 0.50s (0:00:00)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
