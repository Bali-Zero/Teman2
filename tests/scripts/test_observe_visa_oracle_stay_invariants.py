"""Unit tests for the parser in scripts/ci/observe_visa_oracle_stay_invariants.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_stay_invariants import (  # noqa: E402
    CENSUS,
    EXPECTED_BY_FILE,
    REQUIRED_TESTS,
    RESPONSE,
    census_drift,
    missing_tests,
    passed_per_file,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  59 skipped (59)",
        "      Tests  1 failed | 58 passed (59)",
        "      Tests  58 passed | 1 todo (59)",
        "      Tests  58 passed (59)",
        "      Tests  0 passed (0)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


def test_accepts_a_full_pass():
    assert summary_ok("      Tests  59 passed (59)") is True


def _verbose(
    census: int, response: int, titles: tuple[str, ...] = REQUIRED_TESTS
) -> str:
    rows = [f" ✓ {CENSUS} > case {i} 0ms" for i in range(census)]
    rows += [f" ✓ {RESPONSE} > case {i} 0ms" for i in range(response)]
    rows += [f" ✓ engine-adapter.test.ts > {t} 0ms" for t in titles]
    return "\n".join(rows)


def test_exact_census_has_no_drift():
    out = _verbose(EXPECTED_BY_FILE[CENSUS], EXPECTED_BY_FILE[RESPONSE])
    assert census_drift(passed_per_file(out)) == []


@pytest.mark.parametrize(
    "census,response", [(38, 20), (40, 20), (39, 19), (39, 21), (0, 0)]
)
def test_a_lost_or_extra_test_is_drift(census, response):
    assert census_drift(passed_per_file(_verbose(census, response))) != []


def test_all_required_titles_present():
    assert missing_tests(_verbose(1, 1)) == []


def test_a_missing_guilt_title_is_reported():
    kept = REQUIRED_TESTS[1:]
    assert missing_tests(_verbose(1, 1, kept)) == [REQUIRED_TESTS[0]]


def test_a_failed_line_does_not_count_as_run():
    out = " ✗ engine-adapter.test.ts > " + REQUIRED_TESTS[0]
    assert REQUIRED_TESTS[0] in missing_tests(out)
