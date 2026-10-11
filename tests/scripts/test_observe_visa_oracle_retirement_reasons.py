"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_retirement_reasons.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_retirement_reasons import (  # noqa: E402
    REQUIRED_TESTS,
    missing_tests,
    parse_report,
    summary_ok,
)


def _report(passed=150, total=150, failed=0, pending=0, todo=0, success=True, names=()):
    return {
        "success": success,
        "numTotalTests": total,
        "numPassedTests": passed,
        "numFailedTests": failed,
        "numPendingTests": pending,
        "numTodoTests": todo,
        "testResults": [
            {"assertionResults": [{"fullName": n, "status": "passed"} for n in names]}
        ],
    }


@pytest.mark.parametrize(
    "report",
    [
        _report(passed=0, total=100, pending=100),
        _report(passed=99, total=99),
        _report(passed=99, total=100, failed=1, success=False),
        _report(passed=100, total=101, pending=1),
        _report(passed=100, total=101, todo=1),
        _report(passed=99, total=100),
        _report(success=False),
        {},
        None,
        "Tests  150 passed (150)",
    ],
)
def test_rejects_anything_but_a_full_pass(report):
    assert summary_ok(report) is False


@pytest.mark.parametrize("report", [_report(100, 100), _report(150, 150)])
def test_accepts_full_pass_at_or_above_floor(report):
    assert summary_ok(report) is True


def test_parse_report_ignores_log_lines_and_bad_json():
    assert parse_report("noise") is None
    assert parse_report("noise {not json") is None
    assert parse_report('log line\n{"success": true}') == {"success": True}


def test_a_log_line_with_a_required_title_does_not_satisfy_the_gate():
    # Text output (a checkmark line) is not a report: only a passed assertion counts.
    assert parse_report("✓ " + REQUIRED_TESTS[0]) is None


def test_missing_tests_names_a_deleted_or_unpassed_required_test():
    full = _report(names=[f"file > suite > {t}" for t in REQUIRED_TESTS])
    assert missing_tests(full) == []
    partial = _report(names=[f"file > suite > {t}" for t in REQUIRED_TESTS[1:]])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    full["testResults"][0]["assertionResults"][0]["status"] = "skipped"
    assert missing_tests(full) == [REQUIRED_TESTS[0]]


def test_required_titles_are_substrings_of_real_test_titles():
    src = (
        Path(__file__).parent.parent.parent
        / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
    ).read_text()
    for title in REQUIRED_TESTS:
        assert title in src
