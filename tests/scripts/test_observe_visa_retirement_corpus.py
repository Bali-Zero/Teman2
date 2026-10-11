"""Unit tests for the pin-table and summary parsers in scripts/ci/observe_visa_retirement_corpus.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_retirement_corpus import count_rows, pins_ok, summary_ok  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CENSUS = (
    REPO_ROOT
    / "apps/backend-rag/backend/tests/services/visa_engine/test_interview_walk_census.py"
)


def test_the_real_census_file_reads_13_walks_split_10_and_3():
    tally = count_rows(CENSUS.read_text(encoding="utf-8"))
    assert pins_ok(tally) is True
    assert tally == {"_E33E_AND_E33F": 4, "_E33F_ONLY": 6, "_INCOME_BELOW_FLOOR": 3}


@pytest.mark.parametrize(
    "tally",
    [
        {"_E33E_AND_E33F": 4, "_E33F_ONLY": 5, "_INCOME_BELOW_FLOOR": 3},
        {"_E33E_AND_E33F": 4, "_E33F_ONLY": 6, "_INCOME_BELOW_FLOOR": 2},
        {"_E33E_AND_E33F": 3, "_E33F_ONLY": 7, "_INCOME_BELOW_FLOOR": 3},
        {"_E33E_AND_E33F": 4, "_E33F_ONLY": 6, "_INCOME_BELOW_FLOOR": 4},
        {"_E33E_AND_E33F": 0, "_E33F_ONLY": 0, "_INCOME_BELOW_FLOOR": 0},
    ],
)
def test_a_lost_or_extra_walk_or_a_shifted_split_is_rejected(tally):
    assert pins_ok(tally) is False


@pytest.mark.parametrize(
    "line",
    [
        "9 passed in 3.0s",
        "10 failed, 12 passed in 3.0s",
        "12 passed, 1 skipped in 3.0s",
        "12 passed, 1 xfailed in 3.0s",
        "12 passed, 1 error in 3.0s",
        "",
        None,
    ],
)
def test_summary_rejects_anything_but_a_full_pass_at_or_above_the_floor(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    [
        "10 passed in 3.0s",
        "\x1b[32m\x1b[1m10 passed\x1b[0m, \x1b[33m52 deselected\x1b[0m\x1b[32m in 128.5s (0:02:08)\x1b[0m",
    ],
)
def test_summary_accepts_a_full_pass(line):
    assert summary_ok(line) is True
