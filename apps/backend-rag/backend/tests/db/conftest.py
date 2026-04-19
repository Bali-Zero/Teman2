"""
Shared fixtures for db integration tests.

`db_tx` yields a transaction-scoped asyncpg.Connection; the outer
transaction is rolled back at teardown so tests see the schema/state they
expect regardless of execution order.

DB URL resolution order:
1. TEST_DATABASE_URL env var (override for CI / different environments)
2. Default: nuzantara_dev on localhost:5432 (Pro local Postgres)
   - Port 15432 is the Fly.io tunnel; not always running
   - nuzantara_rag DB doesn't exist locally (it's on Fly.io)
   - nuzantara_dev is the local development database
"""
from __future__ import annotations

import os

import pytest_asyncio
import asyncpg


_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


@pytest_asyncio.fixture
async def db_tx() -> asyncpg.Connection:
    conn = await asyncpg.connect(_DEFAULT_DB_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()
