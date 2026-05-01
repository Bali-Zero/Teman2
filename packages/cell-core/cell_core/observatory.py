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
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional["asyncpg.Pool"] = None
_pool_lock_pid: Optional[int] = None  # detect fork without inherit


def is_enabled() -> bool:
    """Return True iff CELL_OBSERVATORY_EMIT env var is the literal 'true' (case-insensitive)."""
    return os.environ.get("CELL_OBSERVATORY_EMIT", "").lower() == "true"


async def _get_or_create_pool() -> "Optional[asyncpg.Pool]":
    """Return the lazy-initialized asyncpg pool, or None if EVENTBUS_DATABASE_URL is unset.

    Returns None also when asyncpg is not installed (cell-core installed
    without the [postgres] optional extra).
    """
    global _pool, _pool_lock_pid
    try:
        import asyncpg
    except ImportError:
        # Cell-core installed without [postgres] extra; observatory disabled.
        return None

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


_INSERT_SQL = (
    "INSERT INTO events_outbox (channel, payload) "
    "VALUES ($1, $2) RETURNING id"
)
_NOTIFY_SQL = "SELECT pg_notify($1, $2)"


async def emit_pulse_observed(
    cell_id: str,
    cell_kind: str,
    pulse_id: str,
    pulse_timestamp_ms: int,
    phase: str,
    sensors: list[dict[str, Any]],
    pulse_result: dict[str, Any],
    homeostatic_state: dict[str, Any],
    scar_signals: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a pulse-observed event to events_outbox + pg_notify.

    No-op when CELL_OBSERVATORY_EMIT != 'true' or EVENTBUS_DATABASE_URL is unset.
    Errors are swallowed (WARN log) — caller MUST NOT block on this.
    """
    if not is_enabled():
        return

    try:
        pool = await _get_or_create_pool()
        if pool is None:
            return

        payload: dict[str, Any] = {
            "event_version": "v1",
            "cell_id": cell_id,
            "cell_kind": cell_kind,
            "pulse_id": pulse_id,
            "pulse_timestamp": pulse_timestamp_ms,
            "phase": phase,
            "sensors": sensors,
            "pulse_result": pulse_result,
            "homeostatic_state": homeostatic_state,
            "scar_signals": scar_signals or [],
            "metadata": metadata or {},
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(_INSERT_SQL, "cell_pulse_observed", json.dumps(payload))
                outbox_id = int(row["id"])
                payload["_outbox_id"] = outbox_id
                await conn.execute(_NOTIFY_SQL, "cell_pulse_observed", json.dumps(payload))
    except Exception as exc:
        logger.warning(
            "cell_observatory emit failed (non-blocking): cell=%s pulse=%s err=%s",
            cell_id, pulse_id, exc,
        )
