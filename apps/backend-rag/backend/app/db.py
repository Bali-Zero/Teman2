"""
backend.app.db — thin module-level pool accessor.

Provides a get_pool() coroutine that returns the asyncpg Pool initialised at
app startup.  Centralises pool access for services that live outside the
FastAPI request/response cycle (EventBus handlers, background workers, etc.)
and that therefore cannot use FastAPI's Depends() mechanism.

Usage:
    from backend.app.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        ...

At app startup (app_factory.py lifespan), call set_pool(db_pool) once the
pool is created so all consumers immediately see it.

In tests, monkey-patch get_pool directly:
    monkeypatch.setattr("backend.app.db.get_pool", fake_get_pool)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# Module-level holder — set once at startup via set_pool().
_pool: "asyncpg.Pool | None" = None


def set_pool(pool: "asyncpg.Pool") -> None:
    """Store the application-level asyncpg pool for later retrieval."""
    global _pool
    _pool = pool


async def get_pool() -> "asyncpg.Pool":
    """Return the asyncpg pool.

    Raises:
        RuntimeError: If the pool has not been initialised yet.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool is not initialised. "
            "Ensure set_pool() is called at app startup before using get_pool()."
        )
    return _pool
