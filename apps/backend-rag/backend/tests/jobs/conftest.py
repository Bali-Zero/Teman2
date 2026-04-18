"""Shared fixtures for backend/jobs tests.

Assumes migration 112 has been applied to whichever DB TEST_DATABASE_URL
(or DATABASE_URL) points at. If neither env var is set, all tests in this
package are skipped at collection time.
"""
from __future__ import annotations

import os

import asyncpg
import pytest

TEST_DB_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)

if not TEST_DB_URL:
    pytest.skip(
        "TEST_DATABASE_URL or DATABASE_URL must be set for jobs tests",
        allow_module_level=True,
    )


@pytest.fixture
async def pg_pool():
    """Asyncpg pool pointed at the test DB.

    Truncates job_runs at fixture acquisition so each test starts from a
    clean slate. The table must already exist (migration 112 must have been
    applied — this is a precondition of the test suite).
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=2, max_size=4)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE job_runs RESTART IDENTITY")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def pg_conn(pg_pool):
    async with pg_pool.acquire() as conn:
        yield conn
