"""Unit tests for the parsers in scripts/ci/observe_visa_oracle_e33_income_wording.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_e33_income_wording import (  # noqa: E402
    REQUIRED_TESTS,
    banned_lines,
    copy_present,
    SENTENCES,
    missing_tests,
    sentence_problems,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  100 skipped (100)",
        "      Tests  99 passed (99)",
        "      Tests  1 failed | 120 passed (121)",
        "      Tests  120 passed | 1 skipped (121)",
        "      Tests  120 passed | 1 todo (121)",
        "      Tests  119 passed (120)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line", ["      Tests  100 passed (100)", "      Tests  130 passed (130)"]
)
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_missing_tests_names_absent_and_skipped_titles():
    ok = "\n".join(f" ✓ suite > {t} 1ms" for t in REQUIRED_TESTS)
    assert missing_tests(ok) == []
    assert missing_tests(ok.replace("✓", "-")) == list(REQUIRED_TESTS)
    assert missing_tests("") == list(REQUIRED_TESTS)


@pytest.mark.parametrize(
    "src",
    [
        '  "Retirement with passive income of USD 3,000.",',
        '  "On a passive-income basis.",',
        '  "Pensiun dengan penghasilan pasif minimal.",',
        '  "PASSIVE INCOME",',
        '  "An income-or-allowance basis.",',
    ],
)
def test_banned_phrase_in_copy_is_caught(src):
    assert banned_lines("a\n" + src) == [2]


def test_banned_phrase_in_a_comment_is_not_copy():
    assert banned_lines("// the monthly passive income below which\nconst a = 1;") == []


def test_clean_copy_has_no_hits_and_required_phrases_present():
    src = '"income or allowance"\n"penghasilan atau tunjangan"'
    assert banned_lines(src) == []
    assert copy_present(src) == []
    assert copy_present("nothing") == ["income or allowance", "penghasilan atau tunjangan"]


def _good_source():
    return "\n".join(f"{a} {p}" for a, p in SENTENCES)


def test_every_sentence_row_passes_on_a_good_source():
    assert sentence_problems(_good_source()) == []


def test_one_sentence_with_a_third_wording_is_caught_individually():
    anchor, phrase = SENTENCES[4]
    bad = _good_source().replace(f"{anchor} {phrase}", f"{anchor} income-or-allowance")
    assert len(sentence_problems(bad)) == 1
    assert sentence_problems(bad)[0].startswith(repr(anchor))


def test_missing_or_duplicated_anchor_is_caught():
    src = _good_source()
    assert len(sentence_problems(src.split("\n", 1)[1])) == 1
    assert len(sentence_problems(src + "\n" + src.split("\n")[0])) == 1
