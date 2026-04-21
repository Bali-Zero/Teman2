"""
Shared fixtures for compliance subsystem tests.

`db_pool` — shared asyncpg.Pool against local test DB.
`db_tx`   — per-test transaction, rolled back at teardown (integration tests).
`sample_client` — inserts a client row inside db_tx and returns its dict.
`sample_forecast` — builds a ComplianceForecast dataclass (no DB).

Schema note: `clients` table has no `preferred_language` column — omitted from insert.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
import pytest_asyncio
import asyncpg

from backend.services.compliance.predictive_engine import ComplianceForecast


_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def db_tx(db_pool: asyncpg.Pool) -> asyncpg.Connection:
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()


@pytest_asyncio.fixture
async def sample_client(db_tx: asyncpg.Connection) -> dict:
    # Minimal client insert — no preferred_language (column does not exist).
    row = await db_tx.fetchrow(
        """
        INSERT INTO clients (full_name, email, created_at, updated_at)
        VALUES ($1, $2, NOW(), NOW())
        RETURNING id, full_name, email
        """,
        "Test Client E2E", "test-e2e@example.com",
    )
    return dict(row)


@pytest.fixture
def sample_forecast() -> ComplianceForecast:
    today = date.today()
    return ComplianceForecast(
        client_id=0,  # overwritten per test
        client_name="Test Client",
        assigned_to=None,
        document_type="visa",
        current_visa_type="C1",
        expiry_date=today + timedelta(days=30),
        days_until_expiry=30,
        matched_rule_id="visa_c1_renewal",
        processing_days=14,
        lead_time_start=today + timedelta(days=16),
        recommended_action_by=today + timedelta(days=16),
        days_until_action=16,
        estimated_revenue_idr=None,
        renewal_pricing_key="visa.c1_renewal",
        priority_score=0.75,
        urgency_level="urgent",
        required_docs=["passport", "sponsor_letter"],
        has_active_renewal_practice=False,
        notes="",
    )
