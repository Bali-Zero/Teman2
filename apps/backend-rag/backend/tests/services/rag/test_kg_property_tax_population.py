"""
Tests for KG Phase 1: Property + Tax Population Script
=======================================================

Validates that the population functions insert the correct number of
nodes and edges, that cross-domain references are correct, and that
dry-run mode does not touch the database.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py -v
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import the module under test
from scripts.kg_populate_property_tax import (
    PROPERTY_CONCEPT_NODES,
    PROPERTY_EDGES,
    PROPERTY_FEE_NODES,
    PROPERTY_TYPE_NODES,
    TAX_DEADLINE_NODES,
    TAX_EDGES,
    TAX_OBLIGATION_NODES,
    TAX_TYPE_NODES,
    populate_property_edges,
    populate_property_nodes,
    populate_tax_edges,
    populate_tax_nodes,
    run_phase1,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_conn() -> AsyncMock:
    """Async mock for asyncpg.Connection — records all execute() calls."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    return conn


@pytest.fixture
def mock_db(mock_conn: AsyncMock) -> tuple[MagicMock, AsyncMock]:
    """
    Returns (pool, conn) where pool.acquire() yields conn.

    pool.acquire is a regular MagicMock (not async) so that
    ``async with pool.acquire() as conn:`` works correctly.

    Usage in tests: pool, conn = mock_db
    """
    pool = MagicMock()
    # Make pool.acquire() work as an async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, mock_conn


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY NODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_populate_property_nodes(mock_conn: AsyncMock) -> None:
    """Verify exactly 4 property_type + 7 concept + 1 fee = 12 nodes inserted."""
    count = await populate_property_nodes(mock_conn)

    expected = len(PROPERTY_TYPE_NODES) + len(PROPERTY_CONCEPT_NODES) + len(PROPERTY_FEE_NODES)
    assert count == expected
    assert count == 12  # 4 + 7 + 1

    # Each node triggers one conn.execute call
    assert mock_conn.execute.call_count == expected


@pytest.mark.asyncio
async def test_property_type_node_count() -> None:
    """There must be exactly 4 property type nodes."""
    assert len(PROPERTY_TYPE_NODES) == 4
    ids = {n["entity_id"] for n in PROPERTY_TYPE_NODES}
    assert "property_type:hak_pakai" in ids
    assert "property_type:hgb" in ids
    assert "property_type:hak_milik" in ids
    assert "property_type:rental" in ids


@pytest.mark.asyncio
async def test_property_node_structure(mock_conn: AsyncMock) -> None:
    """Verify node upsert passes correct SQL args."""
    await populate_property_nodes(mock_conn)

    # First call should be hak_pakai (first in PROPERTY_TYPE_NODES)
    first_call_args = mock_conn.execute.call_args_list[0]
    positional = first_call_args[0]

    # positional[0] is the SQL string
    assert "INSERT INTO kg_nodes" in positional[0]
    # positional[1] is entity_id
    assert positional[1] == "property_type:hak_pakai"
    # positional[2] is entity_type
    assert positional[2] == "property_type"
    # positional[3] is name
    assert positional[3] == "Hak Pakai (Right to Use)"
    # positional[4] is JSON properties
    props = json.loads(positional[4])
    assert props["allowed_for_foreigners"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY EDGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_populate_property_edges(mock_conn: AsyncMock) -> None:
    """Verify >= 10 property edges inserted (spec requires 14)."""
    count = await populate_property_edges(mock_conn)

    assert count >= 10
    assert count == len(PROPERTY_EDGES)
    assert count == 14
    assert mock_conn.execute.call_count == 14


@pytest.mark.asyncio
async def test_property_edge_relationship_id_format(mock_conn: AsyncMock) -> None:
    """relationship_id must follow {source}_{type}_{target} format."""
    await populate_property_edges(mock_conn)

    first_call_args = mock_conn.execute.call_args_list[0][0]
    # positional[1] is relationship_id
    rel_id = first_call_args[1]
    assert rel_id == "property_type:hak_pakai_ALLOWS_OWNERSHIP_concept:foreigner"


# ═══════════════════════════════════════════════════════════════════════════════
# TAX NODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_populate_tax_nodes(mock_conn: AsyncMock) -> None:
    """Verify 5 tax_type + 5 tax_obligation + 2 deadline = 12 nodes."""
    count = await populate_tax_nodes(mock_conn)

    expected_domain = len(TAX_TYPE_NODES) + len(TAX_OBLIGATION_NODES)
    assert expected_domain == 10  # 5 + 5 domain nodes

    total = expected_domain + len(TAX_DEADLINE_NODES)
    assert count == total
    assert count == 12  # 5 + 5 + 2
    assert mock_conn.execute.call_count == total


@pytest.mark.asyncio
async def test_tax_type_node_data() -> None:
    """Tax type nodes must have correct rates and descriptions."""
    pph_badan = next(n for n in TAX_TYPE_NODES if n["entity_id"] == "tax_type:pph_badan")
    assert pph_badan["properties"]["rate"] == 0.22

    ppn = next(n for n in TAX_TYPE_NODES if n["entity_id"] == "tax_type:ppn")
    assert ppn["properties"]["rate"] == 0.11
    assert ppn["properties"]["threshold_idr"] == 4_800_000_000


# ═══════════════════════════════════════════════════════════════════════════════
# TAX EDGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_populate_tax_edges(mock_conn: AsyncMock) -> None:
    """Verify >= 8 tax edges inserted (spec requires 14)."""
    count = await populate_tax_edges(mock_conn)

    assert count >= 8
    assert count == len(TAX_EDGES)
    assert count == 14
    assert mock_conn.execute.call_count == 14


@pytest.mark.asyncio
async def test_tax_has_tax_edges() -> None:
    """HAS_TAX edges connect company entities to tax types."""
    has_tax = [e for e in TAX_EDGES if e["type"] == "HAS_TAX"]
    assert len(has_tax) == 6  # 4 for pt_pma + 2 for cv

    pt_pma_taxes = [e for e in has_tax if e["source"] == "company:pt_pma"]
    assert len(pt_pma_taxes) == 4

    cv_taxes = [e for e in has_tax if e["source"] == "company:cv"]
    assert len(cv_taxes) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-DOMAIN EDGE TEST
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cross_domain_edges() -> None:
    """Verify property_type:hgb -> company:pt_pma cross-domain edge exists."""
    cross = [
        e for e in PROPERTY_EDGES
        if e["source"] == "property_type:hgb" and e["target"] == "company:pt_pma"
    ]
    assert len(cross) == 1
    assert cross[0]["type"] == "REQUIRES_ENTITY"
    assert "evidence" in cross[0]["properties"]


# ═══════════════════════════════════════════════════════════════════════════════
# RUN_PHASE1 TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_phase1_dry_run(mock_conn: AsyncMock) -> None:
    """Dry-run must NOT call conn.execute but still return counts."""
    results = await run_phase1(mock_conn, dry_run=True, phase="all")

    # No DB writes in dry-run
    mock_conn.execute.assert_not_called()

    # But counts should still be reported
    assert results["property_nodes"] == 12
    assert results["property_edges"] == 14
    assert results["tax_nodes"] == 12
    assert results["tax_edges"] == 14


@pytest.mark.asyncio
async def test_run_phase1_real(mock_conn: AsyncMock) -> None:
    """Real mode must call conn.execute for all nodes + edges."""
    results = await run_phase1(mock_conn, dry_run=False, phase="all")

    # Total calls = property_nodes(12) + property_edges(14) + tax_nodes(12) + tax_edges(14) = 52
    assert mock_conn.execute.call_count == 52
    assert results["property_nodes"] == 12
    assert results["property_edges"] == 14
    assert results["tax_nodes"] == 12
    assert results["tax_edges"] == 14


@pytest.mark.asyncio
async def test_run_phase1_property_only(mock_conn: AsyncMock) -> None:
    """Phase 'property' must only insert property nodes/edges."""
    results = await run_phase1(mock_conn, dry_run=False, phase="property")

    assert "property_nodes" in results
    assert "property_edges" in results
    assert "tax_nodes" not in results
    assert "tax_edges" not in results
    assert mock_conn.execute.call_count == 12 + 14  # nodes + edges


@pytest.mark.asyncio
async def test_run_phase1_tax_only(mock_conn: AsyncMock) -> None:
    """Phase 'tax' must only insert tax nodes/edges."""
    results = await run_phase1(mock_conn, dry_run=False, phase="tax")

    assert "tax_nodes" in results
    assert "tax_edges" in results
    assert "property_nodes" not in results
    assert "property_edges" not in results
    assert mock_conn.execute.call_count == 12 + 14  # nodes + edges


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY SUBGRAPH KG-FIRST REWIRE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_property_requirements_from_kg(mock_db: tuple[AsyncMock, AsyncMock]) -> None:
    """get_property_requirements_node queries KG when db_pool provided."""
    from backend.services.rag.kg_subgraph_property import get_property_requirements_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[
        {
            "entity_id": "concept:kitas_or_kitap",
            "name": "KITAS or KITAP Holder",
            "properties": {},
            "relationship_type": "HAS_REQUIREMENT",
        },
        {
            "entity_id": "concept:notary_deed",
            "name": "Notary Deed Execution",
            "properties": {},
            "relationship_type": "HAS_REQUIREMENT",
        },
        {
            "entity_id": "government_fee:bphtb_5pct",
            "name": "BPHTB Tax (5%)",
            "properties": {"rate": "5%"},
            "relationship_type": "HAS_FEE",
        },
    ])

    state = {"property_type": "hak_pakai", "query": "buy hak pakai", "user_context": {}}
    result = await get_property_requirements_node(state, pool)

    assert result["kg_sources_used"] == 3
    assert len(result["property_requirements"]) == 3
    assert result["property_requirements"][0]["type"] == "HAS_REQUIREMENT"


@pytest.mark.asyncio
async def test_property_requirements_fallback(mock_db: tuple[AsyncMock, AsyncMock]) -> None:
    """get_property_requirements_node falls back to hardcoded when KG is empty."""
    from backend.services.rag.kg_subgraph_property import get_property_requirements_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[])

    state = {"property_type": "hak_pakai", "query": "buy hak pakai", "user_context": {}}
    result = await get_property_requirements_node(state, pool)

    assert result["kg_sources_used"] == 0
    assert len(result["property_requirements"]) == 1
    assert result["property_requirements"][0]["requirement_type"] == "ownership"


@pytest.mark.asyncio
async def test_property_workflow_confidence_with_kg() -> None:
    """synthesize_property_workflow_node uses kg_sources_used for confidence."""
    from backend.services.rag.kg_subgraph_property import synthesize_property_workflow_node

    state: dict[str, Any] = {"property_type": "hak_pakai", "kg_sources_used": 3}
    result = await synthesize_property_workflow_node(state)

    # With kg_sources_used > 0, has_db_validation=True -> entity_confidence_avg=0.8
    breakdown = result["workflow"]["confidence_breakdown"]
    assert breakdown["entity_confidence_avg"] == 0.8
    # unique_sources=max(1, 3)=3 -> multi_source_bonus=0.15
    assert breakdown["unique_source_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# TAX SUBGRAPH KG-FIRST TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tax_obligations_from_kg(mock_db):
    """get_tax_obligations_node queries KG when data is available."""
    from backend.services.rag.kg_subgraph_tax import get_tax_obligations_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[
        {
            "entity_id": "tax_type:pph_badan",
            "name": "PPh Badan (Corporate Income Tax)",
            "properties": {"rate": 0.22, "description": "Corporate Income Tax"},
        },
        {
            "entity_id": "tax_type:pph_21",
            "name": "PPh 21 (Employee Withholding)",
            "properties": {"description": "Withholding tax on employee salaries"},
        },
    ])

    state: dict = {
        "query": "tax obligations for PT PMA",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "npwp_required": True,
        "vat_applicable": False,
        "tax_obligations": [],
    }

    result = await get_tax_obligations_node(state, pool)

    assert result["kg_sources_used"] == 2
    tax_overview = result["tax_obligations"][0]
    assert tax_overview["source"] == "knowledge_graph"
    assert "pph_badan" in tax_overview["details"]


@pytest.mark.asyncio
async def test_tax_obligations_fallback(mock_db):
    """get_tax_obligations_node falls back to hardcoded when KG is empty."""
    from backend.services.rag.kg_subgraph_tax import get_tax_obligations_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[])

    state: dict = {
        "query": "tax obligations",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "npwp_required": True,
        "vat_applicable": True,
        "tax_obligations": [],
    }

    result = await get_tax_obligations_node(state, pool)

    assert result.get("kg_sources_used", 0) == 0
    tax_overview = result["tax_obligations"][0]
    assert tax_overview["source"] == "hardcoded_fallback"
    assert "pph_corporate" in tax_overview["details"]


@pytest.mark.asyncio
async def test_tax_workflow_confidence_with_kg():
    """synthesize_tax_workflow_node uses kg_sources_used for confidence."""
    from backend.services.rag.kg_subgraph_tax import synthesize_tax_workflow_node

    state: dict = {
        "query": "tax",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "vat_applicable": False,
        "tax_obligations": [],
        "kg_sources_used": 4,
    }

    result = await synthesize_tax_workflow_node(state)

    # When kg_sources_used > 0, has_db_validation=True → entity_confidence_avg=0.8
    assert result["workflow"]["confidence_breakdown"]["entity_confidence_avg"] == 0.8
    # With 4 unique sources (>=3), multi_source_bonus should be 0.15
    assert result["workflow"]["confidence_breakdown"]["multi_source_bonus"] == 0.15
