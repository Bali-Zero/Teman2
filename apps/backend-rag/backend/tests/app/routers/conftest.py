"""
Shared fixtures for router integration tests.

Provides:
  db_pool  — asyncpg.Pool against local test DB
  db_tx    — per-test transaction, rolled back at teardown
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
