"""`inspect_kbli 62110` returns three defence-industry permits. They are real.

They belong to the five 62xxx computer-programming codes that video-game
development was sourced from when PP 28/2025 — written against the KBLI-2020
numbering — had no row for the new 2025 code. Deleting them would be wrong;
serving them unqualified sends a games studio to the defence ministry.

These tests pin BOTH directions, because a signal that only proves guilt is how
a cure becomes the next defect (cicatrix family #3): an inherited record must
be named, and a self-sourced one must stay silent.
"""

import hashlib
import json
from pathlib import Path

import pytest

from backend.services.kbli_pp28_provenance import (
    content_inherited_from,
    inherited_licensing_note,
    licensing_disclosure,
)

REPO_ROOT = next(
    p
    for p in Path(__file__).resolve().parents
    if (p / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").is_file()
)
DATASET = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


# --------------------------------------------------------------------------
# GUILT — a carried record names where its rows came from
# --------------------------------------------------------------------------


def test_inherited_record_names_its_sources():
    assert content_inherited_from(["62011", "62019"], "62110") == ["62011", "62019"]


def test_note_names_every_source_code_and_plural_agrees():
    note = inherited_licensing_note(["62011", "62019"])
    assert note is not None
    assert "62011" in note and "62019" in note
    assert "KBLI 2020 codes " in note  # plural
    assert "Bali Zero team" in note

    single = inherited_licensing_note(["63111"])
    assert single is not None and "KBLI 2020 code 63111" in single
    assert "KBLI 2020 codes" not in single


def test_the_note_dates_the_codes_it_names_to_the_2020_vintage():
    """The codes in `pp28_sources` are KBLI-2020 numbers, and the note is read
    by clients who will look them up on OUR site, where the catalogue is 2025.

    Measured over the 378 distinct codes this note can name: 345 do not exist
    as 2025 codes (the client finds nothing) and 33 DO — as a DIFFERENT
    activity, because numbers are reused across vintages. `62110`'s five
    sources are all in the first group. Naming a bare number is therefore a
    dangling pointer at best and a wrong page at worst, so the year is part of
    the claim, not formatting. Guard it in BOTH grammatical forms: the plural
    branch is the one 62110 hits, and a fix that reaches only the branch that
    bit you is half a fix.
    """
    for sources in (["62011"], ["62011", "62019", "62015"]):
        note = inherited_licensing_note(sources)
        assert note is not None
        assert "KBLI 2020 code" in note, note
        # An undated "KBLI code 62011" must not survive anywhere in the string.
        assert "from KBLI code" not in note, note
        assert "from KBLI codes" not in note, note


# --------------------------------------------------------------------------
# INNOCENCE — silence is the correct answer three different ways
# --------------------------------------------------------------------------


def test_self_sourced_record_is_not_inherited():
    """Its own code in the list means it HAS a row; extras are supplements."""
    assert content_inherited_from(["56101", "56102"], "56101") is None


def test_nothing_recorded_is_not_an_inheritance_claim():
    """175 codes record no PP 28 source. Absence is not evidence."""
    assert content_inherited_from([], "01111") is None
    assert content_inherited_from(None, "01111") is None


def test_note_is_none_when_there_is_nothing_to_disclose():
    assert inherited_licensing_note(None) is None
    assert inherited_licensing_note([]) is None


# --------------------------------------------------------------------------
# FAIL-SAFE — malformed input must never fabricate a provenance
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["62011", b"62011", 62011, 3.5, {"a": 1}.keys().__iter__])
def test_scalar_or_string_input_yields_silence_not_five_phantom_sources(bad):
    """Iterating the string "62011" would yield five characters — five phantom
    source codes on a record that has none."""
    assert content_inherited_from(bad, "62110") is None


def test_blank_and_whitespace_entries_are_dropped_not_disclosed():
    """`str(None)` is "None" — truthy, and printable to a client as a source
    KBLI code that does not exist. The canonical carries 1,735 entries and all
    1,735 are strings today, so this pins a latent shape, not a live record.
    """
    assert content_inherited_from(["", "  ", None], "62110") is None
    assert content_inherited_from([" 62011 ", "", None, True], "62110") == ["62011"]


def test_own_code_matches_after_stripping():
    assert content_inherited_from([" 56101 "], "56101") is None


# --------------------------------------------------------------------------
# THE RESPONSE DECISION — both halves of the rule, all four combinations
# --------------------------------------------------------------------------


def test_disclosure_names_the_sources_when_the_response_lists_licences():
    codes, note = licensing_disclosure(["62011", "62019"], "62110", has_licenses=True)
    assert codes == ["62011", "62019"]
    assert note is not None and "62011" in note


def test_disclosure_is_silent_when_the_response_lists_no_licences():
    """A note about "the licences listed" on a response that lists none is an
    assertion about nothing — the same class of harm as an unqualified one."""
    codes, note = licensing_disclosure(["62011", "62019"], "62110", has_licenses=False)
    assert codes is None and note is None


def test_disclosure_is_silent_for_a_self_sourced_code_with_licences():
    codes, note = licensing_disclosure(["56101"], "56101", has_licenses=True)
    assert codes is None and note is None


def test_disclosure_is_silent_on_an_unsynced_node():
    """A kg_node that predates the `pp28_sources` sync must degrade to today's
    silence, never to a fabricated provenance."""
    codes, note = licensing_disclosure(None, "62110", has_licenses=True)
    assert codes is None and note is None


def test_the_two_fields_always_agree():
    """One derivation, so a caller cannot ship the codes without the sentence
    or the sentence without the codes."""
    for sources in (["62011"], ["62011", "62019"], [], None):
        for has in (True, False):
            codes, note = licensing_disclosure(sources, "62110", has_licenses=has)
            assert (codes is None) == (note is None)


# --------------------------------------------------------------------------
# CROSS-LANGUAGE PIN — the TypeScript twin asserts the same number
# --------------------------------------------------------------------------


def test_canonical_partition_matches_the_typescript_counterpart():
    """`pp28ContentInheritedFrom` in apps/mouth/src/lib/kbli-provenance.ts
    implements the same rule and its test pins 390 on this same file.

    Two languages cannot share a function, so they share this pin. A COUNT is
    not enough — two divergent implementations can both answer 390 while
    disagreeing about WHICH 390 — so the membership is hashed as well. An
    adversarial review made exactly that point about the first version of this
    test.
    """
    rows = json.loads(DATASET.read_text(encoding="utf-8"))["data"]
    assert len(rows) == 1559, "canonical size changed — re-derive the pins below"

    inherited, self_sourced, unrecorded = [], [], []
    for rec in rows:
        code = str(rec["kode_kbli_2025"])
        verdict = content_inherited_from(rec.get("pp28_sources"), code)
        if verdict:
            inherited.append(code)
        elif rec.get("pp28_sources"):
            self_sourced.append(code)
        else:
            unrecorded.append(code)

    assert len(inherited) == 390
    # WHICH 390, not just how many. Swapping one code for another keeps the
    # count and changes what a client is told about two codes.
    assert (
        hashlib.sha256(",".join(sorted(inherited)).encode()).hexdigest()
        == "a93e90f6e1c174b55ef0316609f4b945c39d0e8b69de2f92be7118fccf9dcf9f"
    )
    # Exhaustive: every code lands in exactly one bucket, so a future field
    # rename cannot quietly shrink the inherited set into a fourth state.
    assert len(inherited) + len(self_sourced) + len(unrecorded) == 1559

    by_code = {str(r["kode_kbli_2025"]): r for r in rows}
    assert "62110" in by_code, "positive control absent — the key is wrong, not the data"
    assert content_inherited_from(by_code["62110"].get("pp28_sources"), "62110") == [
        "62011",
        "62019",
        "62015",
        "62013",
        "62012",
    ]
    # The two innocence controls this cure was proven live against.
    for control in ("56101", "01111"):
        assert content_inherited_from(by_code[control].get("pp28_sources"), control) is None
