"""
Shared fixtures for router integration tests.

Provides:
  db_pool  — asyncpg.Pool against local test DB
  db_tx    — per-test transaction, rolled back at teardown

Tests skip cleanly when the test DB is unreachable or lacks the schema
they need (e.g. CI's empty postgres:15 service container).
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

# Tables every router-integration test in this directory expects to exist.
# If any one is missing the suite skips, since the test setup that adds rows
# (via raw INSERTs, not migrations) would otherwise crash with UndefinedTable.
_REQUIRED_TABLES = ("clients", "compliance_alerts")


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    try:
        pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"router integration tests: DB unreachable ({exc})")
        return  # help static analyzers see pool is unbound on this path

    skip_reason: str | None = None
    try:
        async with pool.acquire() as conn:
            for table in _REQUIRED_TABLES:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = (
                        f"router integration tests: required table '{table}' "
                        "missing (run migrations against the test DB to enable)"
                    )
                    break
        if skip_reason is None:
            yield pool
    finally:
        await pool.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture
async def db_tx(db_pool: asyncpg.Pool) -> asyncpg.Connection:
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()
