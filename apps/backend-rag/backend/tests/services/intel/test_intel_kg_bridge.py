"""
intel_kg_bridge: when Tier 3 finds entities, propose them to kg_proposals
(m108) but DO NOT auto-promote (decision #3).

Schema note: kg_proposals (m108) uses proposal_id as the unique key.
The bridge generates proposal_id = "intel-{staging_id}-{entity_id}".

These are integration tests — they require a real DB connection.
The conftest.py creates kg_proposals table inside the transaction if it
doesn't exist locally (m108 may not be applied yet on nuzantara_dev).
"""
from __future__ import annotations

import pytest
import asyncpg

from backend.services.intel.intel_kg_bridge import propose_kg_entities


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_empty_entities_no_insert(db_tx: asyncpg.Connection) -> None:
    count_before = await db_tx.fetchval("SELECT COUNT(*) FROM kg_proposals")
    await propose_kg_entities(db_tx, staging_id=123, entities=[])
    count_after = await db_tx.fetchval("SELECT COUNT(*) FROM kg_proposals")
    assert count_before == count_after


@pytest.mark.asyncio
async def test_entities_create_one_proposal_per_entity(
    db_tx: asyncpg.Connection,
) -> None:
    staging_id = 999
    entities = [
        {"id": "e1", "name": "BKPM", "type": "org"},
        {"id": "e2", "name": "LKPM", "type": "regulation"},
    ]
    inserted = await propose_kg_entities(db_tx, staging_id=staging_id, entities=entities)
    assert inserted == 2

    rows = await db_tx.fetch(
        "SELECT * FROM kg_proposals WHERE gap_id = $1",
        f"intel_staging:{staging_id}",
    )
    assert len(rows) == 2
    # All proposals must be 'pending' (never auto-promoted)
    assert {r["status"] for r in rows} == {"pending"}
    # All proposals must be in intel domain
    assert {r["domain"] for r in rows} == {"intel"}


@pytest.mark.asyncio
async def test_proposals_are_idempotent(db_tx: asyncpg.Connection) -> None:
    """Second insert with same staging_id + entity_id must be a no-op."""
    entities = [{"id": "e-dup", "name": "X"}]
    first = await propose_kg_entities(db_tx, staging_id=42, entities=entities)
    second = await propose_kg_entities(db_tx, staging_id=42, entities=entities)
    assert first == 1
    assert second == 0  # idempotent

    count = await db_tx.fetchval(
        "SELECT COUNT(*) FROM kg_proposals WHERE proposal_id = 'intel-42-e-dup'",
    )
    assert count == 1
