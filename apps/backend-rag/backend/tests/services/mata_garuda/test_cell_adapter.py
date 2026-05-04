"""Unit tests for mata-garuda cell_adapter — validation + confidence_tier mapping.

DB-touching tests (tag_provenance, get_provenance, list_expired_assets) live
in the integration test layer (W2 Day 6). This file covers the pure-Python
defensive logic so it runs in <50ms on every PR.

Sprint 3 W2 review X1 hardening (2026-05-04 multi-LLM): the
``*_match_ddl`` tests now PARSE the SQL migration's CHECK constraints
and assert the Python constants match the actual DDL — not just match
another hardcoded Python set.
"""
from __future__ import annotations

import re
from pathlib import Path

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


# Path to the migration file that owns the schema's CHECK constraints.
_MIGRATION_154 = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "154_asset_provenance.sql"
)


def _parse_check_in_clause(sql: str, column: str) -> set[str]:
    """Parse `column CHAR/VARCHAR/TEXT … CHECK (column IN ('a','b',...))`.

    Returns the parsed set of allowed values (as strings — caller casts
    to int if needed). Lookups are case-sensitive. Used by X1 hardening
    to verify Python adapter constants vs SQL DDL CHECK enums.
    """
    # Match `column [type] … CHECK (column IN ('a','b',...))`. Tolerant of
    # whitespace + multiline.
    pattern = re.compile(
        rf"\b{re.escape(column)}\b[^,]*?CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\((?P<values>[^)]+)\)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(sql)
    if m is None:
        raise ValueError(
            f"could not find `CHECK ({column} IN (...))` in migration 154 SQL"
        )
    raw = m.group("values")
    # Extract single-quoted literals
    return set(re.findall(r"'([^']+)'", raw))


def _parse_check_between(sql: str, column: str) -> tuple[int, int]:
    """Parse `column SMALLINT … CHECK (column BETWEEN x AND y)`.

    Returns (low, high) inclusive. Caller computes range.
    """
    pattern = re.compile(
        rf"\b{re.escape(column)}\b[^,]*?CHECK\s*\(\s*{re.escape(column)}\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(sql)
    if m is None:
        raise ValueError(
            f"could not find `CHECK ({column} BETWEEN x AND y)` in migration 154 SQL"
        )
    return int(m.group(1)), int(m.group(2))


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
    """X1 hardening: parse the actual CHECK constraint from mig 154.

    Without parsing, this test would be tautological (Python set ==
    Python set), and a typo in the DDL would not fail CI. Now any drift
    between adapter constants and DDL is caught.
    """
    sql = _MIGRATION_154.read_text()
    parsed = _parse_check_in_clause(sql, "reliability")
    assert RELIABILITY_VALUES == frozenset(parsed), (
        f"RELIABILITY_VALUES adapter constant {RELIABILITY_VALUES!r} "
        f"diverges from mig 154 CHECK enum {parsed!r}"
    )


def test_admiralty_credibility_values_match_ddl():
    """X1 hardening: parse `CHECK (credibility BETWEEN x AND y)`."""
    sql = _MIGRATION_154.read_text()
    low, high = _parse_check_between(sql, "credibility")
    expected = frozenset(range(low, high + 1))
    assert CREDIBILITY_VALUES == expected, (
        f"CREDIBILITY_VALUES adapter constant {CREDIBILITY_VALUES!r} "
        f"diverges from mig 154 CHECK BETWEEN {low}..{high}"
    )


def test_tlp_values_match_ddl():
    """X1 hardening: parse the actual CHECK constraint from mig 154."""
    sql = _MIGRATION_154.read_text()
    parsed = _parse_check_in_clause(sql, "tlp")
    assert TLP_VALUES == frozenset(parsed), (
        f"TLP_VALUES adapter constant {TLP_VALUES!r} "
        f"diverges from mig 154 CHECK enum {parsed!r}"
    )


def test_invalidation_modes_match_ddl():
    """X1 hardening: parse the actual CHECK constraint from mig 154."""
    sql = _MIGRATION_154.read_text()
    parsed = _parse_check_in_clause(sql, "invalidation_mode")
    assert INVALIDATION_MODES == frozenset(parsed), (
        f"INVALIDATION_MODES adapter constant {INVALIDATION_MODES!r} "
        f"diverges from mig 154 CHECK enum {parsed!r}"
    )


def test_asset_kind_authoritative_matches_ddl():
    """X1 hardening: ASSET_KIND_AUTHORITATIVE constant must equal the
    12-value CHECK enum in mig 154 (B3 review pin)."""
    sql = _MIGRATION_154.read_text()
    parsed = _parse_check_in_clause(sql, "asset_kind")
    assert set(ASSET_KIND_AUTHORITATIVE) == parsed, (
        f"ASSET_KIND_AUTHORITATIVE constant diverges from mig 154 "
        f"CHECK enum.\nIn-Python: {sorted(ASSET_KIND_AUTHORITATIVE)!r}\n"
        f"In-DDL:    {sorted(parsed)!r}"
    )


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


def test_confidence_tier_explicit_mapping_for_all_36_cells():
    """X1 hardening: assert the EXACT (reliability, credibility) → tier
    mapping for all 6×6=36 cells of the admiralty matrix.

    Previous version only asserted ``tier in {VERIFIED|HIGH|LOW|UNVERIFIED}``
    — a tautology because confidence_tier() always returns a value from
    that set (catch-all UNVERIFIED). It would have passed even if the
    function returned UNVERIFIED for every input. This explicit mapping
    catches any logic regression.
    """
    expected: dict[tuple[str, int], str] = {}
    # VERIFIED: only A1
    expected[("A", 1)] = "VERIFIED"
    # HIGH: A or B with credibility 1-3 (excluding A1)
    for r in ("A", "B"):
        for c in (1, 2, 3):
            if (r, c) == ("A", 1):
                continue
            expected[(r, c)] = "HIGH"
    # LOW: C or D with credibility 1-3
    for r in ("C", "D"):
        for c in (1, 2, 3):
            expected[(r, c)] = "LOW"
    # UNVERIFIED: everything else (E/F any credibility, OR credibility 4-6)
    for r in ("A", "B", "C", "D", "E", "F"):
        for c in (1, 2, 3, 4, 5, 6):
            if (r, c) not in expected:
                expected[(r, c)] = "UNVERIFIED"
    # Sanity: we cover all 36 cells
    assert len(expected) == 36

    for (r, c), tier in expected.items():
        assert confidence_tier(r, c) == tier, (
            f"confidence_tier({r!r}, {c}) returned {confidence_tier(r, c)!r}; "
            f"expected {tier!r}"
        )
