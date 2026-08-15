"""Two merge rules live in one function, and the asymmetry is the point.

The public PMA/Bali/editorial disclosure atom and `pp28_sources` are
AUTHORITATIVE: canonical absence clears stale values.
`pp28_sources` is AUTHORITATIVE and is also REMOVED when canonical drops it,
because `inspect_kbli` renders it into a client-facing sentence naming other
KBLI codes: a stale list would disclose an inheritance the dataset no longer
records, and a wrong provenance claim is worse than no note at all.

Both directions are pinned. A merge tested only where it writes is how a cure
becomes the next defect (cicatrix family #3).
"""

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "kg_kbli_resync.py"
assert _MODULE_PATH.is_file(), f"resync script not at {_MODULE_PATH}"
_SPEC = importlib.util.spec_from_file_location("kg_kbli_resync", _MODULE_PATH)
assert _SPEC and _SPEC.loader
kg_kbli_resync = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kg_kbli_resync)
merge_node_props = kg_kbli_resync.merge_node_props

_REPO_ROOT = _MODULE_PATH.parents[4]
_CANONICAL = json.loads(
    (_REPO_ROOT / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").read_text()
)["data"]
_CANONICAL_BY_CODE = {record["kode_kbli_2025"]: record for record in _CANONICAL}
_REGISTRY = json.loads(
    (_REPO_ROOT / "data" / "kbli-filiera" / "pma-editorial-certifications.json").read_text()
)


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
    assert out["pma_status"] == "NOT_VERIFIED"
    assert out["pma_verification_status"] == "declared_gap"
    assert out["pma_cap_verified"] is False
    assert "pma_max_asing" not in out
    assert "pma_official_basis" not in out
    assert "pma_source_vintage" not in out


def test_complete_located_pma_tuple_is_copied_exactly():
    canonical = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_verification_status": "located",
        "pma_official_basis": "Perpres 49/2021 Lampiran III entry 3",
        "pma_source_vintage": "2021-05-25",
    }
    out = merge_node_props({}, canonical)
    assert {key: out[key] for key in canonical} == canonical
    assert out["pma_cap_verified"] is False


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
    assert out["pma_status"] == "NOT_VERIFIED"
    assert out["pma_verification_status"] == "declared_gap"
    assert "pma_max_asing" not in out
    assert "pma_official_basis" not in out
    assert "pma_source_vintage" not in out


# --------------------------------------------------------------------------
# EDITORIAL ATOM + INNOCENCE
# --------------------------------------------------------------------------


def test_a_gap_removes_stale_intel_keys_atomically():
    existing = {k: f"value-{k}" for k in kg_kbli_resync.INTEL_KEYS}
    out = merge_node_props(existing, {"intel_2026": {}})
    for key in kg_kbli_resync.INTEL_KEYS:
        assert key not in out


def test_a_gap_removes_all_known_editorial_and_bali_claims() -> None:
    existing = {key: f"stale-{key}" for key in kg_kbli_resync.EDITORIAL_KEYS} | {
        "bali_status": "OK_or_HIGHER_RISK",
        "bali_blocked": False,
        "bali_reason": "stale",
        "has_bali_l4": True,
        "l4_bali": {"status": "OK_or_HIGHER_RISK", "blocked": False},
    }

    out = merge_node_props(existing, {"pma_status": "TERBUKA"})

    assert not any(key in out for key in kg_kbli_resync.EDITORIAL_KEYS)
    assert "bali_status" not in out
    assert "bali_blocked" not in out
    assert out["has_bali_l4"] is False
    assert "l4_bali" not in out


def test_located_tuple_syncs_intel_and_typed_bali_authoritatively() -> None:
    canonical = {
        **_CANONICAL_BY_CODE["47111"],
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": True,
            "reason": "moratorium",
        },
    }

    out = merge_node_props(
        {"whatItMeans": "stale", "whatChanged": "stale", "bali_status": "stale"},
        canonical,
        _REGISTRY,
    )

    assert out["whatItMeans"] == canonical["intel_2026"]["whatItMeans"]
    assert out["whatYouNeed"] == canonical["intel_2026"]["whatYouNeed"]
    assert out["whatChanged"] == canonical["intel_2026"]["whatChanged"]
    assert out["zantaraOpener"] == (
        "Ask me about KBLI 47111: its official scope, licensing, risk, "
        "or foreign-ownership verification."
    )
    assert out["bali_status"] == "CHIUSO_MORATORIA_BALI"
    assert out["bali_blocked"] is True
    assert out["has_bali_l4"] is True


def test_located_but_uncertified_intel_is_removed_atomically() -> None:
    canonical = _CANONICAL_BY_CODE["47222"]
    assert canonical["pma_verification_status"] == "located"
    assert "47222" not in _REGISTRY["canonicalIntel"]

    out = merge_node_props(
        {key: f"stale-{key}" for key in kg_kbli_resync.EDITORIAL_KEYS},
        canonical,
        _REGISTRY,
    )

    assert not any(key in out for key in kg_kbli_resync.EDITORIAL_KEYS)


def test_malformed_bali_boolean_is_neutral_not_truthiness_coerced() -> None:
    canonical = {
        "pma_status": "TERBUKA",
        "pma_verification_status": "located",
        "pma_official_basis": "official locator",
        "pma_source_vintage": "2021-05-25",
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": "false",
            "reason": "unsafe",
        },
    }

    out = merge_node_props({}, canonical)

    assert "bali_status" not in out
    assert "bali_blocked" not in out
    assert out["has_bali_l4"] is False


def test_local_disclosure_matches_the_shared_runtime_contract() -> None:
    from backend.services.kbli_pma_disclosure import disclose_bali, disclose_pma

    canonical = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 49,
        "pma_verification_status": "located",
        "pma_official_basis": " official locator ",
        "pma_source_vintage": " 2021-05-25 ",
        "l4_bali": {"status": "NON_CLASSIFICABILE", "blocked": False},
    }

    assert kg_kbli_resync._disclose_pma(canonical) == disclose_pma(canonical)
    assert kg_kbli_resync._disclose_bali(canonical) == disclose_bali(canonical)


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
