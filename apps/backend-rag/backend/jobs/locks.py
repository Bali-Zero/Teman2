"""Postgres advisory locks for jobs runner concurrency guarantees.

Keys are arbitrary strings. We hash to a signed int64 (PG's pg_advisory_lock
argument type) with SHA-1 truncation and sign mapping. Collisions between
distinct keys are statistically negligible for the registry sizes we see
(order of tens of jobs × tens of ticks/day).
"""
from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg


def stable_hash_int64(key: str) -> int:
    """Map arbitrary string to a signed int64 stable across processes."""
    digest = hashlib.sha1(key.encode("utf-8")).digest()[:8]
    # Interpret big-endian as signed 64-bit.
    return int.from_bytes(digest, byteorder="big", signed=True)


@asynccontextmanager
async def advisory_lock(
    conn: asyncpg.Connection, key: str
) -> AsyncIterator[bool]:
    """Non-blocking advisory lock. Yields True if acquired, False otherwise.

    Always releases on context exit; releasing a non-acquired lock is a no-op.
    """
    lock_id = stable_hash_int64(key)
    got: bool = bool(
        await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
    )
    try:
        yield got
    finally:
        if got:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
