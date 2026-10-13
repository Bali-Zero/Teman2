"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_no_door_replay_freshness.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_no_door_replay_freshness import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  4 skipped (4)",
        "      Tests  3 passed (3)",
        "      Tests  1 failed | 3 passed (4)",
        "      Tests  4 passed | 1 skipped (5)",
        "      Tests  4 passed | 1 todo (5)",
        "      Tests  3 passed (4)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  4 passed (4)", "      Tests  5 passed (5)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
