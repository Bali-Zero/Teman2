"""Unit tests for the verdict in scripts/ci/observe_visa_oracle_penjamin_copy.py."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_penjamin_copy import MIN_TESTS, REQUIRED_TESTS, verdict  # noqa: E402


def good() -> dict:
    cases = [
        {"title": t, "fullName": f"suite {t}", "status": "passed"} for t in REQUIRED_TESTS
    ]
    cases += [
        {"title": f"t{i}", "fullName": f"suite t{i}", "status": "passed"}
        for i in range(MIN_TESTS)
    ]
    n = len(cases)
    return {
        "success": True,
        "numTotalTests": n,
        "numPassedTests": n,
        "numFailedTests": 0,
        "numPendingTests": 0,
        "numTodoTests": 0,
        "testResults": [{"assertionResults": cases}],
    }


def test_accepts_a_full_pass():
    assert verdict(good()) == []


@pytest.mark.parametrize("bad", [None, [], "Tests  80 passed (80)", {}])
def test_rejects_non_reports_and_forged_text(bad):
    assert verdict(bad) != []


def test_rejects_failed_pending_todo_and_reduced_counts():
    for key in ("numFailedTests", "numPendingTests", "numTodoTests"):
        r = good()
        r[key] = 1
        assert verdict(r) != []
    r = good()
    r["numPassedTests"] -= 1
    assert verdict(r) != []
    r = good()
    r["success"] = False
    assert verdict(r) != []


def test_rejects_required_test_missing_skipped_or_failed():
    for status in ("skipped", "failed", "todo"):
        r = good()
        r["testResults"][0]["assertionResults"][0]["status"] = status
        assert any("required test" in p for p in verdict(r))
    r = good()
    del r["testResults"][0]["assertionResults"][0]
    assert any("required test" in p for p in verdict(r))


def test_a_forged_title_in_another_field_does_not_count():
    r = copy.deepcopy(good())
    case = r["testResults"][0]["assertionResults"][0]
    case["title"] = "other"
    case["fullName"] = "suite other"
    case["ancestorTitles"] = [REQUIRED_TESTS[0]]
    assert any("required test" in p for p in verdict(r))
