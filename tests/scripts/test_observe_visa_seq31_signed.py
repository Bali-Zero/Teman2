"""Unit tests for the summary parser in scripts/ci/observe_visa_seq31_signed.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_seq31_signed import EXPECTED_SIGNED_SEQUENCE, TEST_MODULES, summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "34 passed in 4.93s",
        "1 failed, 35 passed in 0.03s",
        "35 passed, 1 skipped in 0.03s",
        "35 passed, 1 xfailed in 0.03s",
        "35 passed, 1 warning in 0.03s",
        "36 passed, 1 error in 0.03s",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line, 35) is False


@pytest.mark.parametrize(
    "line", ["35 passed in 4.93s", "===== 36 passed in 1.20s =====", "35 passed in 0.50s (0:00:00)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line, 35) is True


def test_skips_are_tolerated_only_up_to_the_declared_maximum():
    assert summary_ok("69 passed, 14 skipped in 50.44s", 69, 14) is True
    assert summary_ok("69 passed, 15 skipped in 50.44s", 69, 14) is False


def test_ansi_colour_is_stripped_before_the_line_is_judged():
    assert summary_ok("\x1b[32m\x1b[1m35 passed\x1b[0m in 4.93s", 35) is True
    assert summary_ok("\x1b[31m1 failed\x1b[0m, 35 passed in 4.93s", 35) is False


def test_the_observer_is_pinned_to_seq31_and_runs_its_own_pack_gate_and_the_census():
    assert EXPECTED_SIGNED_SEQUENCE == 31
    modules = {module: (floor, skips) for module, floor, skips in TEST_MODULES}
    assert modules["backend/tests/services/visa_engine/test_seq31_pack.py"] == (39, 0)
    assert modules["backend/tests/services/visa_engine/test_interview_walk_census.py"] == (111, 14)
