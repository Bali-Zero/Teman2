"""Unit tests for the summary parser in scripts/ci/observe_llms_e33_gov_routes.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_llms_e33_gov_routes import summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  29 skipped (29)",
        "      Tests  28 passed (28)",
        "      Tests  1 failed | 28 passed (29)",
        "      Tests  29 passed | 1 skipped (30)",
        "      Tests  29 passed | 1 todo (30)",
        "      Tests  28 passed (29)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  29 passed (29)", "      Tests  30 passed (30)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True
