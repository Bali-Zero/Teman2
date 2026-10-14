"""Unit tests for the parsers in scripts/ci/observe_visa_oracle_e33f_note.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_e33f_note import (  # noqa: E402
    MIN_TESTS,
    REQUIRED_TESTS,
    missing_tests,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        f"      Tests  {MIN_TESTS} skipped ({MIN_TESTS})",
        f"      Tests  {MIN_TESTS - 1} passed ({MIN_TESTS - 1})",
        f"      Tests  1 failed | {MIN_TESTS} passed ({MIN_TESTS + 1})",
        f"      Tests  {MIN_TESTS} passed | 1 skipped ({MIN_TESTS + 1})",
        f"      Tests  {MIN_TESTS} passed | 1 todo ({MIN_TESTS + 1})",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


def test_accepts_full_pass_at_or_above_floor():
    assert summary_ok(f"      Tests  {MIN_TESTS} passed ({MIN_TESTS})") is True
    assert summary_ok(f"      Tests  {MIN_TESTS + 5} passed ({MIN_TESTS + 5})") is True


def test_missing_tests_names_a_deleted_required_test():
    full = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS)
    assert missing_tests(full) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in REQUIRED_TESTS[1:])
    assert missing_tests(partial) == [REQUIRED_TESTS[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped) == [REQUIRED_TESTS[0]]


PACK_SCAN_TITLES = (
    "innocence: the newest signed pack has no problems (E33E-only rules are the four named, each twin identical)",
    "the E33E-only rules are exactly the hard filters with identical twins plus el.e33e.retirement and the disputed-band rule",
    "el.e33e.retirement is the E33F rule plus age 55 or more plus the deposit trio",
    "the disputed-band rule never excludes and itself requires the deposit trio",
    "no rule targets both E33E and E33F",
    "the note's EN and ID figures equal the pack's deposit threshold",
    "the note names the state-owned bank and the own-name condition in EN and ID",
    "a harmless new identical twin pair does not fail the scan",
    "guilt: a changed deposit threshold fails the scan",
    "guilt: removing the deposit clause from el.e33e.retirement fails the scan",
    "guilt: appending an age cap to el.e33e.retirement fails the scan",
    "guilt: appending a second deposit leaf to el.e33e.retirement fails the scan",
    "guilt: appending a contradictory state-bank leaf to el.e33e.retirement fails the scan",
    "guilt: a new E33E-only EXCLUDE rule fails the scan",
    "guilt: a new E33F-only SUPPORT rule fails the scan",
    "guilt: adding or removing a global rule fails the scan",
    "guilt: a twin whose on_unknown differs fails the scan",
    "guilt: el.e33e.retirement no longer covering RETIREMENT fails the scan",
    "guilt: el.e33e.retirement with a closed validity period fails the scan",
    "guilt: turning the disputed-band rule into an EXCLUDE fails the scan",
    "guilt: a rule that targets both products fails the scan",
)


def test_pack_scan_guard_is_observed_and_its_titles_are_required():
    import observe_visa_oracle_e33f_note as obs

    assert any(f.endswith("e33e-e33f-pack-scan.test.ts") for f in obs.TEST_FILES)
    assert len(PACK_SCAN_TITLES) == 21
    assert set(PACK_SCAN_TITLES) <= set(REQUIRED_TESTS)
