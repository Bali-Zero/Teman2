"""Retry DDL that cannot immediately acquire a PostgreSQL table lock."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

import asyncpg

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_PATTERN = re.compile(r"^\d+(ms|s|min)$")


async def run_ddl_with_lock_timeout(
    conn: asyncpg.Connection,
    fn: Callable[[asyncpg.Connection], Awaitable[None]],
    *,
    lock_timeout: str = "5s",
    attempts: int = 3,
    sleep_seconds: float = 2.0,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Run DDL with a bounded lock wait and retry on unavailable locks."""
    if not _LOCK_TIMEOUT_PATTERN.fullmatch(lock_timeout):
        raise ValueError(f"Invalid lock_timeout: {lock_timeout!r}")

    await conn.execute(f"SET lock_timeout = '{lock_timeout}'")

    for attempt in range(1, attempts + 1):
        try:
            await fn(conn)
            return
        except asyncpg.exceptions.LockNotAvailableError:
            logger.warning("DDL lock unavailable (attempt %d/%d)", attempt, attempts)
            if attempt == attempts:
                raise
            await sleeper(sleep_seconds)
