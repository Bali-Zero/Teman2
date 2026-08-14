"""Two merge rules live in one function, and the asymmetry is the point.

The complete `pma_*` evidence tuple and `pp28_sources` are AUTHORITATIVE:
canonical absence clears stale values. Intel keys remain additive.
`pp28_sources` is AUTHORITATIVE and is also REMOVED when canonical drops it,
because `inspect_kbli` renders it into a client-facing sentence naming other
KBLI codes: a stale list would disclose an inheritance the dataset no longer
records, and a wrong provenance claim is worse than no note at all.

Both directions are pinned. A merge tested only where it writes is how a cure
becomes the next defect (cicatrix family #3).
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "kg_kbli_resync.py"
assert _MODULE_PATH.is_file(), f"resync script not at {_MODULE_PATH}"
_SPEC = importlib.util.spec_from_file_location("kg_kbli_resync", _MODULE_PATH)
assert _SPEC and _SPEC.loader
kg_kbli_resync = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kg_kbli_resync)
merge_node_props = kg_kbli_resync.merge_node_props


# --------------------------------------------------------------------------
# pp28_sources — the authoritative field
# --------------------------------------------------------------------------


def test_writes_the_sources_the_canonical_records():
    out = merge_node_props({}, {"pp28_sources": ["62011", "62019"]})
    assert out["pp28_sources"] == ["62011", "62019"]


def test_clears_a_stale_list_when_the_canonical_no_longer_records_one():
    """GUILT for the rule that justifies the asymmetry: leaving this behind
    makes `inspect_kbli` name source codes the dataset has withdrawn."""
    out = merge_node_props({"pp28_sources": ["62011"]}, {"pp28_sources": []})
    assert "pp28_sources" not in out

    out = merge_node_props({"pp28_sources": ["62011"]}, {})
    assert "pp28_sources" not in out


def test_a_malformed_value_clears_rather_than_propagates():
    """A scalar where a list belongs is not an inheritance claim."""
    out = merge_node_props({"pp28_sources": ["62011"]}, {"pp28_sources": "62011"})
    assert "pp28_sources" not in out


def test_drops_entries_that_are_not_codes_instead_of_writing_None():
    out = merge_node_props({}, {"pp28_sources": [" 62011 ", "", None, True, "62019"]})
    assert out["pp28_sources"] == ["62011", "62019"]


# --------------------------------------------------------------------------
# PMA evidence tuple — authoritative as one unit
# --------------------------------------------------------------------------


def test_absent_pma_tuple_clears_stale_graph_values():
    existing = {key: f"stale-{key}" for key in kg_kbli_resync.PMA_KEYS}
    out = merge_node_props(existing, {"pp28_sources": ["62011"]})
    assert not any(key in out for key in kg_kbli_resync.PMA_KEYS)


def test_complete_located_pma_tuple_is_copied_exactly():
    canonical = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_verification_status": "located",
        "pma_official_basis": "Perpres 49/2021 Lampiran III entry 3",
        "pma_source_vintage": "2021-05-25",
    }
    out = merge_node_props({}, canonical)
    assert {key: out[key] for key in kg_kbli_resync.PMA_KEYS} == canonical


def test_partial_canonical_tuple_removes_stale_locator_and_vintage():
    existing = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_verification_status": "located",
        "pma_official_basis": "old basis",
        "pma_source_vintage": "old vintage",
    }
    out = merge_node_props(
        existing,
        {
            "pma_status": "TERBUKA",
            "pma_max_asing": 100,
            "pma_verification_status": "declared_gap",
        },
    )
    assert out["pma_status"] == "TERBUKA"
    assert out["pma_max_asing"] == 100
    assert out["pma_verification_status"] == "declared_gap"
    assert "pma_official_basis" not in out
    assert "pma_source_vintage" not in out


# --------------------------------------------------------------------------
# INNOCENCE — additive intel and unrelated fields remain additive
# --------------------------------------------------------------------------


def test_absent_intel_keys_do_not_null_the_graph_values():
    existing = {k: f"value-{k}" for k in kg_kbli_resync.INTEL_KEYS}
    out = merge_node_props(existing, {"intel_2026": {}})
    for key in kg_kbli_resync.INTEL_KEYS:
        assert out[key] == f"value-{key}"


def test_untouched_properties_survive():
    """Fields with unknown original derivation (kategori_risiko, skala_usaha,
    licensing_status, sektor_id) are left alone by contract."""
    out = merge_node_props(
        {"kategori_risiko": "MR", "skala_usaha": ["Besar"], "licensing_status": "REGULATED"},
        {"pma_status": "TERBUKA"},
    )
    assert out["kategori_risiko"] == "MR"
    assert out["skala_usaha"] == ["Besar"]
    assert out["licensing_status"] == "REGULATED"


def test_does_not_mutate_the_input_properties():
    """`main()` compares `new_props == props` to decide whether to write at
    all; an in-place merge would make every row look unchanged."""
    props = {"pma_status": "TERBUKA"}
    merge_node_props(props, {"pma_status": "TERBATAS", "pp28_sources": ["62011"]})
    assert props == {"pma_status": "TERBUKA"}


@pytest.mark.parametrize(
    "rec",
    [
        {"pma_verification_status": "declared_gap"},
        {"intel_2026": {"whatItMeans": "x"}},
        {"pp28_sources": ["62011"]},
    ],
)
def test_each_field_alone_is_enough_to_produce_a_change(rec):
    assert merge_node_props({}, rec) != {}
