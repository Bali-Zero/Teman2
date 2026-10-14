"""Unit tests for the summary parser in scripts/ci/observe_visa_oracle_stay_permit_length.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_stay_permit_length import FILES, missing_tests, summary_ok  # noqa: E402


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  100 skipped (100)",
        "      Tests  99 passed (99)",
        "      Tests  1 failed | 99 passed (100)",
        "      Tests  100 passed | 1 skipped (101)",
        "      Tests  100 passed | 1 todo (101)",
        "      Tests  99 passed (100)",
        "",
        None,
    ],
)
def test_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line, 100) is False


@pytest.mark.parametrize("line", ["      Tests  100 passed (100)", "      Tests  101 passed (101)"])
def test_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line, 100) is True


def test_every_file_names_required_titles_and_a_minimum():
    assert len(FILES) == 3
    for test_file, minimum, required in FILES:
        assert test_file.endswith((".test.ts", ".test.tsx"))
        assert minimum >= 1
        assert required


def test_missing_tests_names_a_deleted_or_skipped_required_test():
    _, _, required = FILES[1]
    full = "\n".join(f" ✓ file > suite > {t}" for t in required)
    assert missing_tests(full, required) == []
    partial = "\n".join(f" ✓ file > suite > {t}" for t in required[1:])
    assert missing_tests(partial, required) == [required[0]]
    skipped = full.replace("✓", "-", 1)
    assert missing_tests(skipped, required) == [required[0]]
