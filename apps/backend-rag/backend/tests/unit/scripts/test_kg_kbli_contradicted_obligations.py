"""Guilt + innocence for the contradicted-obligations edge cure.

The shapes below are the ones measured on prod on 2026-08-05, because the whole
value of this cure is that it separates the wrong edge from the right one ON THE
SAME CODE — `79122` (Umrah/Hajj travel) was being told to clear plantation land
without burning while ALSO carrying its genuine pilgrimage duties. A whole-code
cure would have taken both; the innocence tests here are what pin that it does
not.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "kg_kbli_contradicted_obligations.py"
)
_spec = importlib.util.spec_from_file_location("kg_kbli_contradicted_obligations", _MODULE_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
# Register BEFORE exec: @dataclass resolves annotations via
# sys.modules[cls.__module__], which is None for an unregistered module.
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)


# --- the live strings this cure exists for --------------------------------
FARMING = "Menerapkan cara budi daya tanaman pangan yang baik (good agriculture practices) dan"
LAND_CLEARING = (
    "Menerapkan teknologi pembukaan lahan tanpa bakar dan mengelola sumber daya alam secara lestari"
)
PILGRIM_GUIDE = "Menyediakan paling sedikit 1 (satu) orang pembimbing ibadah dari setiap rombongan"
ACCREDITATION = "Memperoleh akreditasi setiap 5 (lima) tahun"
INDUSTRY_DATA = "Memiliki bukti penyampaian wajib Data Industri tervalidasi setiap 6 (enam) bulan"
SARA_FREE = "Menjamin konten dalam produk tidak mengandung konten SARA dan"


def record(*obligations: str, scales: int = 1) -> dict:
    """A canonical record whose per_skala entries carry `obligations`."""
    return {
        "kode_kbli_2025": "00000",
        "per_skala": [{"skala_usaha": ["Besar"], "kewajiban": list(obligations)}] * scales,
    }


# --- guilt ----------------------------------------------------------------


def test_a_pilgrimage_agency_told_to_clear_land_without_burning_is_contradicted():
    canon = mod.canonical_obligations(record(ACCREDITATION, PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, [LAND_CLEARING]) == mod.CONTRADICTED


def test_a_game_studio_told_to_apply_good_agriculture_practices_is_contradicted():
    canon = mod.canonical_obligations(record(SARA_FREE))
    assert mod.edge_verdict(canon, [FARMING]) == mod.CONTRADICTED


def test_the_bare_word_skala_is_not_an_obligation_this_code_holds():
    canon = mod.canonical_obligations(record(SARA_FREE))
    assert mod.edge_verdict(canon, ["skala"]) == mod.CONTRADICTED


# --- innocence: the same code keeps what canonical does support -----------


def test_the_pilgrimage_agency_keeps_its_own_pilgrimage_duty():
    canon = mod.canonical_obligations(record(ACCREDITATION, PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, [PILGRIM_GUIDE]) == mod.SUPPORTED


def test_the_game_studio_keeps_its_industry_data_reporting_duty():
    canon = mod.canonical_obligations(record(SARA_FREE, INDUSTRY_DATA))
    assert mod.edge_verdict(canon, [INDUSTRY_DATA]) == mod.SUPPORTED


def test_one_matching_obligation_is_enough_even_beside_unmatched_ones():
    """A target legitimately bundles several duties; canonical need only confirm
    that the target belongs to this code, not every line it carries."""
    canon = mod.canonical_obligations(record(PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, ["something canonical never says", PILGRIM_GUIDE]) == (
        mod.SUPPORTED
    )


# --- the three refusals ---------------------------------------------------


def test_a_target_stating_no_obligation_is_never_judged():
    """`license:nib` and the document nodes carry no `kewajiban` — there is
    nothing to compare, so this cure has no opinion and must not delete."""
    canon = mod.canonical_obligations(record(SARA_FREE))
    verdict = mod.edge_verdict(canon, [])
    assert verdict == mod.CANNOT_JUDGE_NODE_SILENT
    assert not mod.is_deletable(verdict)


def test_a_canonical_record_that_states_nothing_never_authorises_a_delete():
    """Absence of a statement is not a denial — and deleting here would remove
    the only obligation text we hold for that code."""
    verdict = mod.edge_verdict(mod.canonical_obligations(record()), [FARMING])
    assert verdict == mod.CANNOT_JUDGE_CANONICAL_SILENT
    assert not mod.is_deletable(verdict)


def test_a_code_absent_from_canonical_never_authorises_a_delete():
    verdict = mod.edge_verdict(mod.canonical_obligations(None), [FARMING])
    assert verdict == mod.CANNOT_JUDGE_CODE_ABSENT
    assert not mod.is_deletable(verdict)


def test_canonical_obligations_distinguishes_absent_record_from_silent_one():
    """None and set() must not collapse: they drive two different refusals."""
    assert mod.canonical_obligations(None) is None
    assert mod.canonical_obligations(record()) == set()


# --- one normaliser, both sides ------------------------------------------


@pytest.mark.parametrize(
    "node_form",
    [
        f"<strong>{PILGRIM_GUIDE}</strong>",
        PILGRIM_GUIDE.upper(),
        f"  {PILGRIM_GUIDE}\n\n ",
        PILGRIM_GUIDE.replace(" ", "  "),
    ],
)
def test_markup_case_and_whitespace_do_not_manufacture_a_contradiction(node_form):
    canon = mod.canonical_obligations(record(PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, [node_form]) == mod.SUPPORTED


def test_the_canonical_side_is_normalised_too_not_just_the_node_side():
    canon = mod.canonical_obligations(record(f"<li>{PILGRIM_GUIDE}</li>"))
    assert mod.edge_verdict(canon, [PILGRIM_GUIDE]) == mod.SUPPORTED


def test_non_string_obligations_are_dropped_rather_than_crashing():
    canon = mod.canonical_obligations(record(PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, [None, 42, {"a": 1}]) == mod.CANNOT_JUDGE_NODE_SILENT


def test_an_html_entity_does_not_manufacture_a_contradiction():
    """108 canonical obligation strings carry HTML entities and no KG node string
    does, so without decoding the SAME sentence reads CONTRADICTED and the edge
    is deleted. Found by a cross-family review, measured 0 live flips today."""
    canon = mod.canonical_obligations(record("Memenuhi syarat A & B"))
    assert mod.edge_verdict(canon, ["Memenuhi syarat A &amp; B"]) == mod.SUPPORTED


def test_entities_are_decoded_on_the_canonical_side_too():
    canon = mod.canonical_obligations(record("Memenuhi syarat A &amp; B"))
    assert mod.edge_verdict(canon, ["Memenuhi syarat A & B"]) == mod.SUPPORTED


# --- a shape we cannot read is a refusal, never a delete -----------------


def test_a_bare_string_kewajiban_is_refused_not_iterated_character_by_character():
    """`properties.kewajiban` is unvalidated JSON. Iterating a STRING yields
    CHARACTERS: with canonical holding a one-letter entry the node would read
    SUPPORTED off a misparse, and otherwise the whole node would be DELETED on
    one. Neither verdict is evidence about the law."""
    canon = mod.canonical_obligations(record("a"))
    verdict = mod.edge_verdict(canon, "abc")
    assert verdict == mod.CANNOT_JUDGE_NODE_UNREADABLE
    assert not mod.is_deletable(verdict)


def test_a_dict_kewajiban_is_refused_rather_than_judged_on_its_keys():
    canon = mod.canonical_obligations(record(PILGRIM_GUIDE))
    assert mod.edge_verdict(canon, {PILGRIM_GUIDE: 1}) == mod.CANNOT_JUDGE_NODE_UNREADABLE


def test_absent_kewajiban_is_silent_not_unreadable():
    """None must stay distinguishable from a broken shape — the first is the
    ordinary `license:nib` case, the second is a data defect worth seeing."""
    assert mod._obligation_list(None) == []
    assert mod._obligation_list("abc") is None


# --- only CONTRADICTED is deletable --------------------------------------


@pytest.mark.parametrize(
    "verdict,deletable",
    [
        (mod.CONTRADICTED, True),
        (mod.SUPPORTED, False),
        (mod.CANNOT_JUDGE_NODE_SILENT, False),
        (mod.CANNOT_JUDGE_NODE_UNREADABLE, False),
        (mod.CANNOT_JUDGE_CANONICAL_SILENT, False),
        (mod.CANNOT_JUDGE_CODE_ABSENT, False),
    ],
)
def test_is_deletable_admits_exactly_one_outcome(verdict, deletable):
    assert mod.is_deletable(verdict) is deletable


def test_plan_code_asks_is_deletable_instead_of_holding_its_own_opinion(monkeypatch):
    """Wiring pin, made non-tautological after a cross-family review: comparing
    `plan.detach` against `is_deletable(plan.verdicts[...])` passes just as well
    when `plan_code` hard-codes `== CONTRADICTED`, because the two agree today.
    Redefining `is_deletable` to admit SUPPORTED instead is the only way to show
    which of the two the plan actually consults."""
    monkeypatch.setattr(mod, "is_deletable", lambda verdict: verdict == mod.SUPPORTED)
    plan = mod.plan_code(
        "79122",
        record(ACCREDITATION, PILGRIM_GUIDE),
        {
            "perizinan:55be853cd247": [LAND_CLEARING],  # CONTRADICTED
            "perizinan:7a471f5d56b8": [PILGRIM_GUIDE],  # SUPPORTED
        },
    )
    assert plan.detach == ["perizinan:7a471f5d56b8"]


# --- the per-code plan ----------------------------------------------------


def test_the_wrong_target_goes_and_the_right_ones_stay_on_the_same_code():
    plan = mod.plan_code(
        "79122",
        record(ACCREDITATION, PILGRIM_GUIDE),
        {
            "perizinan:55be853cd247": [LAND_CLEARING],
            "perizinan:7a471f5d56b8": [PILGRIM_GUIDE],
            "license:nib": [],
        },
    )
    assert plan.detach == ["perizinan:55be853cd247"]
    assert plan.kept == 2
    assert plan.verdicts["perizinan:7a471f5d56b8"] == mod.SUPPORTED
    assert plan.verdicts["license:nib"] == mod.CANNOT_JUDGE_NODE_SILENT


def test_a_detached_target_is_archived_with_the_obligation_that_condemned_it():
    plan = mod.plan_code("79122", record(ACCREDITATION), {"perizinan:55be853cd247": [LAND_CLEARING]})
    assert plan.archive["perizinan:55be853cd247"] == mod._norm(LAND_CLEARING)


def test_a_code_whose_canonical_is_silent_produces_no_detachments_at_all():
    plan = mod.plan_code("00000", record(), {"perizinan:0bf540b11cf6": [FARMING]})
    assert plan.detach == []
    assert plan.archive == {}


# --- the archive never loses what an earlier run wrote --------------------


def test_merge_archive_keeps_an_earlier_runs_entries():
    merged = mod.merge_archive({"perizinan:aaa": "old"}, {"perizinan:bbb": "new"})
    assert merged == {"perizinan:aaa": "old", "perizinan:bbb": "new"}


def test_merge_archive_is_idempotent_on_a_re_detach():
    first = mod.merge_archive(None, {"perizinan:aaa": "why"})
    assert mod.merge_archive(first, {"perizinan:aaa": "why"}) == first


def test_merge_archive_does_not_blank_a_legacy_non_dict_value():
    merged = mod.merge_archive(["perizinan:legacy"], {"perizinan:aaa": "why"})
    assert merged["perizinan:aaa"] == "why"
    assert "perizinan:legacy" in merged["_legacy"]
