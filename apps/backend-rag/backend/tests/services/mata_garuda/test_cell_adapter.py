"""Unit tests for mata-garuda cell_adapter — validation + confidence_tier mapping.

DB-touching tests (tag_provenance, get_provenance, list_expired_assets) live
in the integration test layer (W2 Day 6). This file covers the pure-Python
defensive logic so it runs in <50ms on every PR.
"""
from __future__ import annotations

import pytest

from backend.services.mata_garuda.cell_adapter import (
    ASSET_KIND_AUTHORITATIVE,
    CREDIBILITY_VALUES,
    INVALIDATION_MODES,
    RELIABILITY_VALUES,
    TLP_VALUES,
    confidence_tier,
    _validate_inputs,
)


def test_authoritative_set_has_exactly_12_values():
    """B3: pin asset_kind to 12 canonical Bali-Zero-domain values."""
    assert len(ASSET_KIND_AUTHORITATIVE) == 12


def test_authoritative_set_contains_canonical_values():
    canonical = {
        "war_room_draft", "war_room_post", "intel_finding",
        "research_dossier", "cross_dossier_thesis", "weekly_strategic_brief",
        "ultra_move", "kg_entity", "kg_proposal", "crm_enrichment_lookup",
        "compliance_alert", "measurer_metric",
    }
    assert set(ASSET_KIND_AUTHORITATIVE) == canonical


def test_authoritative_set_excludes_handover_alternates():
    """The handover-side OSINT-generic list must NOT leak in."""
    forbidden = {
        "news_article", "regulation", "kbli_code", "telegram_post",
        "kg_node", "kg_edge", "contradiction", "entity_link",
        "document_hash", "visa_type", "query_result",
    }
    assert set(ASSET_KIND_AUTHORITATIVE).isdisjoint(forbidden)


def test_admiralty_reliability_values_match_ddl():
    assert RELIABILITY_VALUES == frozenset({"A", "B", "C", "D", "E", "F"})


def test_admiralty_credibility_values_match_ddl():
    assert CREDIBILITY_VALUES == frozenset({1, 2, 3, 4, 5, 6})


def test_tlp_values_match_ddl():
    assert TLP_VALUES == frozenset({"white", "green", "amber", "red", "black"})


def test_invalidation_modes_match_ddl():
    assert INVALIDATION_MODES == frozenset({"auto", "manual", "never"})


# ---------------------------------------------------------------------------
# _validate_inputs — defensive enum check
# ---------------------------------------------------------------------------


def test_validate_inputs_accepts_canonical_values():
    """The happy path should not raise."""
    _validate_inputs(
        asset_kind="war_room_post",
        reliability="A",
        credibility=1,
        invalidation_mode="auto",
        tlp="red",
    )


def test_validate_inputs_rejects_non_canonical_asset_kind():
    with pytest.raises(ValueError, match="canonical 12-value set"):
        _validate_inputs(
            asset_kind="news_article",   # NOT canonical
            reliability="A",
            credibility=1,
            invalidation_mode="auto",
            tlp="red",
        )


def test_validate_inputs_rejects_invalid_reliability():
    with pytest.raises(ValueError, match="reliability"):
        _validate_inputs(
            asset_kind="war_room_post",
            reliability="Z",    # not A-F
            credibility=1,
            invalidation_mode="auto",
            tlp="red",
        )


def test_validate_inputs_rejects_invalid_credibility():
    with pytest.raises(ValueError, match="credibility"):
        _validate_inputs(
            asset_kind="war_room_post",
            reliability="A",
            credibility=0,      # not 1-6
            invalidation_mode="auto",
            tlp="red",
        )


def test_validate_inputs_rejects_invalid_credibility_high():
    with pytest.raises(ValueError, match="credibility"):
        _validate_inputs(
            asset_kind="war_room_post",
            reliability="A",
            credibility=7,      # not 1-6
            invalidation_mode="auto",
            tlp="red",
        )


def test_validate_inputs_rejects_invalid_invalidation_mode():
    with pytest.raises(ValueError, match="invalidation_mode"):
        _validate_inputs(
            asset_kind="war_room_post",
            reliability="A",
            credibility=1,
            invalidation_mode="forever",   # not auto/manual/never
            tlp="red",
        )


def test_validate_inputs_rejects_invalid_tlp():
    with pytest.raises(ValueError, match="tlp"):
        _validate_inputs(
            asset_kind="war_room_post",
            reliability="A",
            credibility=1,
            invalidation_mode="auto",
            tlp="purple",      # not in TLP_VALUES
        )


# ---------------------------------------------------------------------------
# confidence_tier — admiralty matrix → 4-tier collapse
# ---------------------------------------------------------------------------


def test_confidence_tier_A1_is_VERIFIED():
    """A1 = completely reliable + confirmed = VERIFIED (the only single-cell tier)."""
    assert confidence_tier("A", 1) == "VERIFIED"


def test_confidence_tier_A2_to_B3_is_HIGH():
    """Solid sources (A, B) with credibility 1-3 → HIGH."""
    for reliability in ("A", "B"):
        for credibility in (1, 2, 3):
            if (reliability, credibility) == ("A", 1):
                continue   # A1 is its own tier
            assert confidence_tier(reliability, credibility) == "HIGH", \
                f"{reliability}{credibility} expected HIGH"


def test_confidence_tier_C_D_credibility_1_to_3_is_LOW():
    """Fair-to-unusually reliable sources, credibility 1-3 → LOW."""
    for reliability in ("C", "D"):
        for credibility in (1, 2, 3):
            assert confidence_tier(reliability, credibility) == "LOW", \
                f"{reliability}{credibility} expected LOW"


def test_confidence_tier_E_F_always_UNVERIFIED():
    """Unreliable (E) or cannot-judge (F) → UNVERIFIED regardless of credibility."""
    for reliability in ("E", "F"):
        for credibility in (1, 2, 3, 4, 5, 6):
            assert confidence_tier(reliability, credibility) == "UNVERIFIED", \
                f"{reliability}{credibility} expected UNVERIFIED"


def test_confidence_tier_credibility_4_to_6_always_UNVERIFIED():
    """Credibility 4+ (doubtful, improbable, cannot judge) collapses regardless of source."""
    for reliability in ("A", "B", "C", "D"):
        for credibility in (4, 5, 6):
            assert confidence_tier(reliability, credibility) == "UNVERIFIED", \
                f"{reliability}{credibility} expected UNVERIFIED"


def test_confidence_tier_covers_all_30_cells():
    """Sanity: every (reliability, credibility) cell maps to exactly one tier."""
    valid_tiers = {"VERIFIED", "HIGH", "LOW", "UNVERIFIED"}
    for reliability in ("A", "B", "C", "D", "E", "F"):
        for credibility in (1, 2, 3, 4, 5, 6):
            tier = confidence_tier(reliability, credibility)
            assert tier in valid_tiers, \
                f"{reliability}{credibility} mapped to unknown tier {tier!r}"
