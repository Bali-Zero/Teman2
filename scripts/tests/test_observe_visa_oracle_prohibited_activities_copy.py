"""Guilt and innocence for the PR-20 prohibited-activities observer's verdict helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[1]
    / "ci"
    / "observe_visa_oracle_prohibited_activities_copy.py"
)
_SPEC = importlib.util.spec_from_file_location("observe_vo_prohibited", _PATH)
assert _SPEC and _SPEC.loader
obs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(obs)


def test_a_full_pass_is_accepted() -> None:
    assert obs.summary_ok("      Tests  8 passed (8)")


def test_failures_skips_and_reduced_counts_are_rejected() -> None:
    assert not obs.summary_ok("      Tests  1 failed | 7 passed (8)")
    assert not obs.summary_ok("      Tests  7 passed | 1 skipped (8)")
    assert not obs.summary_ok("      Tests  7 passed (7)")
    assert not obs.summary_ok(None)


def test_a_deleted_required_test_is_named() -> None:
    out = "\n".join(f" ✓ file > {t} 1ms" for t in obs.REQUIRED_TESTS[1:])
    assert obs.missing_tests(out) == [obs.REQUIRED_TESTS[0]]


def test_all_required_tests_present_is_innocent() -> None:
    out = "\n".join(f" ✓ file > {t} 1ms" for t in obs.REQUIRED_TESTS)
    assert obs.missing_tests(out) == []
    assert obs.missing_tests(" ✗ file > " + obs.REQUIRED_TESTS[0]) == list(
        obs.REQUIRED_TESTS
    )
