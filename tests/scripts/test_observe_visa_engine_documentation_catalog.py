"""Unit tests for the summary parser in scripts/ci/observe_visa_engine_documentation_catalog.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_engine_documentation_catalog import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "========== 19 passed in 0.02s ==========",
        "========== 19 skipped in 0.02s ==========",
        "========== 18 passed in 0.02s ==========",
        "========== 1 passed in 0.02s ==========",
        "========== 1 failed, 19 passed in 0.02s ==========",
        "========== 19 passed, 1 skipped in 0.02s ==========",
        "========== 19 passed, 1 error in 0.02s ==========",
        "========== 19 passed, 1 xfailed in 0.02s ==========",
        "========== 19 passed, 2 deselected in 0.02s ==========",
        "19 passed, 1 skipped in 0.02s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    [
        "========== 20 passed in 0.02s ==========",
        "========== 20 passed in 1.20s (0:00:01) ==========",
        "========== 20 passed, 1 warning in 0.02s ==========",
        "20 passed in 0.04s",
    ],
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
