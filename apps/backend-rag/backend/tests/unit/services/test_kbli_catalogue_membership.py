"""The catalogue-membership verdict, in both directions.

A guard that only proves it convicts is half a guard: the expensive failure here is not
missing a phantom, it is convicting 1,559 real codes because the catalogue went missing.
So every test below has a twin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services.kbli_catalogue_membership import (
    ABSENT,
    CANONICAL,
    CATALOGUE_FLOOR,
    PHANTOM_LICENSING_STATUS,
    TOMBSTONE_TITLE_SUFFIX,
    UNKNOWN,
    catalogue_verdict,
    is_absent_from_catalogue,
)

# The live table on 2026-09-19: 1,559 canonical + 4 rows already labelled phantom.
LIVE_CATALOGUE_SIZE = 1563


def _rows(size: int, present: int) -> list[dict[str, int]]:
    return [{"catalogue_size": size, "canonical_rows": present}]


# --- GUILT: codes that really are absent, with the catalogue evidently present ---


def test_a_code_with_no_canonical_row_is_absent() -> None:
    assert catalogue_verdict(_rows(LIVE_CATALOGUE_SIZE, 0)) == ABSENT
    assert is_absent_from_catalogue(_rows(LIVE_CATALOGUE_SIZE, 0))


def test_the_four_already_labelled_phantoms_are_absent() -> None:
    """26120, 60111, 82920, 85598 hold a row, but it is labelled NOT_IN_KBLI_2025.

    The query excludes labelled rows, so they arrive here as `canonical_rows == 0` —
    the same shape as the six codes that have no row at all. One verdict, two histories.
    """
    assert catalogue_verdict(_rows(LIVE_CATALOGUE_SIZE, 0)) == ABSENT


# --- INNOCENCE: nothing else may be convicted ---


def test_a_code_with_a_canonical_row_is_canonical() -> None:
    assert catalogue_verdict(_rows(LIVE_CATALOGUE_SIZE, 1)) == CANONICAL
    assert not is_absent_from_catalogue(_rows(LIVE_CATALOGUE_SIZE, 1))


@pytest.mark.parametrize("size", [0, 1, CATALOGUE_FLOOR - 1])
def test_a_catalogue_below_the_floor_never_convicts(size: int) -> None:
    """An empty or truncated catalogue must not turn every code into a tombstone.

    This is the failure that matters: the cure is worth ten codes, and getting this
    direction wrong would cost all 1,559.
    """
    assert catalogue_verdict(_rows(size, 0)) == UNKNOWN
    assert not is_absent_from_catalogue(_rows(size, 0))


def test_no_rows_is_unknown_not_absent() -> None:
    """A fake connection that answers `[]` — as every existing router test's does —
    must leave the endpoint's behaviour untouched."""
    assert catalogue_verdict([]) == UNKNOWN
    assert catalogue_verdict(None) == UNKNOWN
    assert not is_absent_from_catalogue([])


@pytest.mark.parametrize(
    "row",
    [
        {},
        {"catalogue_size": LIVE_CATALOGUE_SIZE},
        {"canonical_rows": 0},
        {"catalogue_size": None, "canonical_rows": 0},
        {"catalogue_size": "many", "canonical_rows": 0},
    ],
)
def test_an_illegible_answer_is_unknown(row: dict) -> None:
    assert catalogue_verdict([row]) == UNKNOWN


def test_the_floor_itself_is_admissible() -> None:
    """Boundary stated explicitly so a future edit cannot move it by accident."""
    assert catalogue_verdict(_rows(CATALOGUE_FLOOR, 0)) == ABSENT
    assert catalogue_verdict(_rows(CATALOGUE_FLOOR - 1, 0)) == UNKNOWN


# --- ANTI-DRIFT: the strings are duplicated from the cure script on purpose ---


def _cure_script_source() -> str:
    path = Path(__file__).resolve().parents[3] / "scripts" / "kbli_documents_phantom_cure.py"
    assert path.exists(), path
    return path.read_text(encoding="utf-8")


def test_the_status_string_matches_the_cure_script() -> None:
    """This service reads what `kbli_documents_phantom_cure.py` writes.

    The constant is duplicated rather than imported (request-time service vs one-shot
    operator script), so the two are pinned together here instead of by an import.
    """
    src = _cure_script_source()
    found = re.search(r'^LICENSING_STATUS\s*=\s*"([^"]+)"', src, re.MULTILINE)
    assert found, "LICENSING_STATUS not found in the cure script"
    assert found.group(1) == PHANTOM_LICENSING_STATUS


def test_the_title_suffix_matches_the_cure_script() -> None:
    src = _cure_script_source()
    found = re.search(r'^VINTAGE_SUFFIX\s*=\s*"([^"]+)"', src, re.MULTILINE)
    assert found, "VINTAGE_SUFFIX not found in the cure script"
    assert found.group(1) == TOMBSTONE_TITLE_SUFFIX
