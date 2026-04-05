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
def mock_db(mock_conn: AsyncMock) -> tuple[AsyncMock, AsyncMock]:
    """
    Returns (pool, conn) where pool.acquire() yields conn.

    Usage in tests: pool, conn = mock_db
    """
    pool = AsyncMock()
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
