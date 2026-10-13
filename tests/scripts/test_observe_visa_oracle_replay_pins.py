"""Unit tests for the parser in scripts/ci/observe_visa_oracle_replay_pins.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_replay_pins import (
    EXPECTED_TESTS,
    REQUIRED_TESTS,
    highest_signed_pack,
    missing_tests,
    replay_drift,
    summary_ok,
)  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  150 skipped (150)",
        "      Tests  149 passed (149)",
        "      Tests  1 failed | 150 passed (151)",
        "      Tests  150 passed | 1 todo (151)",
        "      Tests  250 passed (250)",
        "      Tests  251 passed (251)",
        "      Tests  253 passed (253)",
        "      Tests  150 passed (151)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


def test_accepts_only_the_exact_census():
    assert summary_ok(f"      Tests  {EXPECTED_TESTS} passed ({EXPECTED_TESTS})") is True
    assert summary_ok("      Tests  150 passed (150)") is False


def test_missing_tests_names_a_deleted_required_test():
    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]


def test_replay_drift_catches_a_hand_edited_but_coherent_fixture():
    fresh = {"pack": {"file": "rulepack-prod-029.signed.json", "sequence": 29}, "walks": [1, 2]}
    assert replay_drift(dict(fresh), dict(fresh), "rulepack-prod-029.signed.json") == []
    edited = {**fresh, "walks": [1]}
    assert replay_drift(edited, fresh, "rulepack-prod-029.signed.json")
    stale = {"pack": {"file": "rulepack-prod-028.signed.json", "sequence": 28}, "walks": [1, 2]}
    assert replay_drift(stale, stale, "rulepack-prod-029.signed.json")
    renamed = {**fresh, "pack": {"file": "rulepack-prod-029.signed.json", "sequence": 28}}
    assert replay_drift(renamed, fresh, "rulepack-prod-029.signed.json")


def test_the_active_pack_is_the_highest_signed_file_on_disk():
    assert highest_signed_pack().startswith("rulepack-prod-")
