"""Cell pulse observatory emitter.

Writes pulse events directly to the EventBus events_outbox via asyncpg,
then triggers pg_notify on the 'cell_pulse_observed' channel. Designed
to run inside any cell process (standalone LaunchAgent or in-app), with
NO dependency on backend-rag's Python package — that was BLOCKER B1
from the 2026-05-01 cross-LLM review.

Failures are swallowed (WARN log) — pulse loop must NEVER block on
observability.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock_pid: Optional[int] = None  # detect fork without inherit


def is_enabled() -> bool:
    """Return True iff CELL_OBSERVATORY_EMIT env var is the literal 'true' (case-insensitive)."""
    return os.environ.get("CELL_OBSERVATORY_EMIT", "").lower() == "true"


async def _get_or_create_pool() -> Optional[asyncpg.Pool]:
    """Return the lazy-initialized asyncpg pool, or None if EVENTBUS_DATABASE_URL is unset."""
    global _pool, _pool_lock_pid

    current_pid = os.getpid()
    if _pool_lock_pid is not None and _pool_lock_pid != current_pid:
        # Process forked since pool creation; pool is invalid in child.
        _pool = None
        _pool_lock_pid = None

    if _pool is not None:
        return _pool

    dsn = os.environ.get("EVENTBUS_DATABASE_URL")
    if not dsn:
        return None

    _pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=3,
        command_timeout=5.0,
    )
    _pool_lock_pid = current_pid
    return _pool


def _reset_pool_for_tests() -> None:
    """Internal test hook — DO NOT use in production."""
    global _pool, _pool_lock_pid
    _pool = None
    _pool_lock_pid = None
