"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_retirement_no_sponsor.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_retirement_no_sponsor import (  # noqa: E402
    guard_present,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  190 skipped (190)",
        "      Tests  189 passed (189)",
        "      Tests  1 failed | 189 passed (190)",
        "      Tests  190 passed | 1 skipped (191)",
        "      Tests  190 passed | 1 todo (191)",
        "      Tests  189 passed (190)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  190 passed (190)", "      Tests  200 passed (200)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_the_pack_scan_guard_block_is_in_the_test_file():
    assert guard_present() is True
