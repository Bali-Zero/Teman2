"""
Shared fixtures for intel subsystem tests.

`db_pool` — asyncpg.Pool against local test DB (nuzantara_dev).
`db_tx`   — per-test transaction, rolled back at teardown (integration tests).

Note: kg_proposals table (m108) must exist in nuzantara_dev.
If it doesn't exist, the integration tests create it within the transaction
(CREATE TABLE IF NOT EXISTS inside tx — rolled back after each test).
"""
from __future__ import annotations

import os

import asyncpg
import pytest
import pytest_asyncio

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

# SQL to create kg_proposals table if it doesn't exist (m108 schema)
_CREATE_KG_PROPOSALS = """
CREATE TABLE IF NOT EXISTS kg_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gap_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    proposal_type TEXT NOT NULL CHECK(
        proposal_type IN ('node', 'edge', 'property')
    ),
    node_label TEXT,
    node_type TEXT,
    node_properties JSONB DEFAULT '{}',
    source_entity_id TEXT,
    target_entity_id TEXT,
    relationship_type TEXT,
    edge_properties JSONB DEFAULT '{}',
    target_entity_id_prop TEXT,
    property_key TEXT,
    property_value JSONB,
    evidence_sources JSONB DEFAULT '[]',
    self_rag_score FLOAT NOT NULL DEFAULT 0.0,
    tier TEXT NOT NULL DEFAULT 'tier1_simple',
    research_method TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(
        status IN (
            'pending', 'approved', 'rejected',
            'applied', 'auto_expired'
        )
    ),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    rejection_reason TEXT,
    metadata JSONB DEFAULT '{}'
);
"""


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def db_tx(db_pool: asyncpg.Pool) -> asyncpg.Connection:
    """Per-test transaction, rolled back at teardown.

    Also ensures kg_proposals table exists (for local dev without m108).
    The CREATE TABLE IF NOT EXISTS runs inside the transaction and rolls back
    cleanly — test data never persists.
    """
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            # Ensure kg_proposals exists for bridge integration tests
            await conn.execute(_CREATE_KG_PROPOSALS)
            yield conn
        finally:
            await tx.rollback()
