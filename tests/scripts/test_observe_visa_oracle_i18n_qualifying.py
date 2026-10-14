"""Unit tests for the parsers in scripts/ci/observe_visa_oracle_i18n_qualifying.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_i18n_qualifying import (  # noqa: E402
    I18N_FILE,
    INVEST_ID_LINE,
    MIN_TESTS,
    MOUTH_DIR,
    OLD_INVEST_ID_LINE,
    RETIREMENT_ID_LINE,
    REQUIRED_TESTS,
    missing_tests,
    source_problems,
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
        f"      Tests  {MIN_TESTS - 1} passed ({MIN_TESTS})",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    [
        f"      Tests  {MIN_TESTS} passed ({MIN_TESTS})",
        f"      Tests  {MIN_TESTS + 5} passed ({MIN_TESTS + 5})",
    ],
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_missing_tests_names_absent_and_skipped_titles():
    ok = "\n".join(f" ✓ suite > {t} 1ms" for t in REQUIRED_TESTS)
    assert missing_tests(ok) == []
    assert missing_tests(ok.replace("✓", "-")) == list(REQUIRED_TESTS)
    assert missing_tests("") == list(REQUIRED_TESTS)


def _good_source() -> str:
    return "\n".join(
        [
            '  "q.investment_vehicle.opt.property": "A qualifying property arrangement",',
            f"  {INVEST_ID_LINE}",
            f"  {RETIREMENT_ID_LINE}",
            '  "q.secondhome_basis.opt.property": "Properti yang memenuhi syarat",',
        ]
    )


def test_good_source_and_live_i18n_file_have_no_problems():
    assert source_problems(_good_source()) == []
    real_source = (MOUTH_DIR / I18N_FILE).read_text(encoding="utf-8")
    assert source_problems(real_source) == []


def test_old_value_present_is_caught():
    pre_fix = _good_source().replace(INVEST_ID_LINE, OLD_INVEST_ID_LINE)
    problems = source_problems(pre_fix)
    assert problems != []


def test_rejected_hybrid_wording_is_caught():
    bad = _good_source().replace(
        INVEST_ID_LINE,
        '"q.investment_vehicle.opt.property": "Pengaturan properti yang memenuhi syarat",',
    )
    problems = source_problems(bad)
    assert any("Pengaturan properti yang memenuhi syarat" in p for p in problems)


def test_duplicated_or_missing_lines_are_caught():
    duplicated_invest = _good_source() + f"\n  {INVEST_ID_LINE}"
    assert source_problems(duplicated_invest) != []

    duplicated_pengaturan = _good_source() + f"\n  {RETIREMENT_ID_LINE}"
    assert source_problems(duplicated_pengaturan) != []

    missing_pengaturan = _good_source().replace(f"  {RETIREMENT_ID_LINE}\n", "")
    assert source_problems(missing_pengaturan) != []
