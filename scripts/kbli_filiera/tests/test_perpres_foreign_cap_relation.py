"""Guilt, innocence, and pins on a transcription that no machine can re-derive.

The relation in `perpres_foreign_cap_relation.py` was read off page images
because the PDF text layer corrupts both the codes and the percentages. Nothing
downstream can regenerate it, so the shape of the transcription is pinned here:
if someone "tidies" a row, these fail rather than the catalogue silently gaining
a different law.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from perpres_foreign_cap_relation import (  # noqa: E402
    INSTRUMENT,
    RELATION,
    caps_by_code,
    classify_join,
    main,
    relation_rows,
)


def _record(code_2025: str, ancestors: list[str], cap, status="TERBUKA", judul="x") -> dict:
    return {
        "kode_kbli_2025": code_2025,
        "judul": judul,
        "pma_max_asing": cap,
        "pma_status": status,
        "bps_2020_ancestors": {"codes": ancestors, "source_locator": ["p.1"]},
    }


# --- pins on the transcription itself -------------------------------------

def test_pin_the_document_has_37_entries_41_pairs_40_codes():
    assert {e for e, *_ in RELATION} == set(range(1, 38))
    assert len(RELATION) == 41
    assert len({c for _, _, c, _, _ in RELATION}) == 40


def test_pin_30111_is_the_only_code_the_law_gives_two_different_caps():
    conflicting = {c for c, v in caps_by_code(RELATION).items() if len({x[2] for x in v}) > 1}
    assert conflicting == {"30111"}, (
        "entry 7 caps 30111 at 49% as a warship yard, entry 8 at 0% as a builder of "
        "traditional wooden vessels; if this set changes, the join's ambiguity handling "
        "covers a different population than the one it was written for"
    )


def test_pin_domestic_100_percent_rows_are_recorded_as_ZERO_foreign():
    """The document's column names the DOMESTIC share. Reading 'Modal dalam
    negeri 100%' as a 100% foreign cap inverts the most restrictive rows in the
    instrument into the most permissive ones."""
    by_code = {c: v for c, v in caps_by_code(RELATION).items()}
    for code in ("79122", "90011", "10761"):
        assert {x[2] for x in by_code[code]} == {0}


def test_pin_locator_names_the_operative_instrument_not_the_superseded_one():
    assert "49/2021" in INSTRUMENT and "10/2021" not in INSTRUMENT
    assert all("49/2021" in r["locator"] for r in relation_rows())


# --- guilt -----------------------------------------------------------------

def test_guilt_a_catalogue_record_contradicting_the_law_is_reported():
    res = classify_join(RELATION, [_record("25200", ["25200"], 100)])
    assert [i["kbli_2025"] for i in res["disagree"]] == ["25200"]
    assert res["disagree"][0]["law_caps"] == [49]
    assert res["agree"] == []


def test_guilt_a_zero_percent_activity_sold_as_fully_open_is_reported():
    res = classify_join(RELATION, [_record("79122", ["79122"], 100)])
    assert len(res["disagree"]) == 1 and res["disagree"][0]["law_caps"] == [0]


# --- innocence -------------------------------------------------------------

def test_innocence_a_record_matching_the_law_is_never_a_divergence():
    res = classify_join(RELATION, [_record("25200", ["25200"], 49, status="TERBATAS")])
    assert res["disagree"] == []
    assert [i["kbli_2025"] for i in res["agree"]] == ["25200"]


def test_innocence_a_code_the_instrument_does_not_mention_is_not_judged():
    res = classify_join(RELATION, [_record("62010", ["62010"], 100)])
    assert res["agree"] == res["disagree"] == res["ambiguous"] == []


# --- the ambiguity the LAW creates, not our uncertainty --------------------

@pytest.mark.parametrize("catalogue_cap", [0, 49, 100, None])
def test_a_two_cap_code_is_always_ambiguous_never_auto_patchable(catalogue_cap):
    """Even when the catalogue happens to match one of the two lawful values,
    the code stays ambiguous: which cap applies depends on the bidang usaha, and
    a cure that picked either one would be asserting a fact the instrument does
    not give per-code."""
    res = classify_join(RELATION, [_record("30111", ["30111"], catalogue_cap)])
    assert res["disagree"] == [] and res["agree"] == []
    assert [i["kbli_2025"] for i in res["ambiguous"]] == ["30111"]
    assert res["ambiguous"][0]["law_caps"] == [0, 49]


# --- lineage ---------------------------------------------------------------

def test_a_restricted_2020_code_with_no_2025_heir_is_reported_not_dropped():
    res = classify_join(RELATION, [])
    assert {i["kbli_2020"] for i in res["no_descendant"]} == {c for _, _, c, _, _ in RELATION}


def test_an_unrecognised_ancestry_shape_never_invents_a_lineage():
    weird = {"kode_kbli_2025": "25200", "pma_max_asing": 100,
             "bps_2020_ancestors": "25200"}          # a string, not the dict shape
    res = classify_join(RELATION, [weird])
    assert res["disagree"] == [] and res["agree"] == []
    assert "25200" in {i["kbli_2020"] for i in res["no_descendant"]}


# --- the deliberate non-arming ---------------------------------------------

def test_check_exits_zero_while_the_backlog_exists_and_strict_is_the_flip(tmp_path, capsys):
    dataset = tmp_path / "canon.json"
    dataset.write_text('{"data": [%s]}' % (
        '{"kode_kbli_2025": "25200", "judul": "x", "pma_max_asing": 100, '
        '"pma_status": "TERBUKA", "bps_2020_ancestors": {"codes": ["25200"]}}'
    ))
    assert main(["--check", "--dataset", str(dataset)]) == 0
    assert main(["--check", "--strict", "--dataset", str(dataset)]) == 1
    assert "DISAGREE 1" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path, monkeypatch):
    import perpres_foreign_cap_relation as mod
    sentinel = tmp_path / "must-not-appear.json"
    monkeypatch.setattr(mod, "OUT_PATH", sentinel)
    dataset = tmp_path / "canon.json"
    dataset.write_text('{"data": []}')
    assert mod.main(["--check", "--dataset", str(dataset)]) == 0
    assert not sentinel.exists()
