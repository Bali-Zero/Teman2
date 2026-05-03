"""
Bridge outbox retention — clean up events older than 30 days.

Called by a separate cron (or invoked manually). Idempotent.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


RETENTION_DAYS = 30


async def prune_outbox(conn: Any, retention_days: int = RETENTION_DAYS) -> int:
    """Delete bridge_outbox events older than retention_days. Returns row count."""
    result = await conn.execute(
        f"DELETE FROM bridge_outbox WHERE created_at < NOW() - INTERVAL '{int(retention_days)} days'"
    )
    # asyncpg returns "DELETE N" for this command
    try:
        deleted = int(result.split()[-1]) if result else 0
    except (ValueError, IndexError):
        deleted = 0
    logger.info("Bridge outbox retention: deleted %d rows older than %d days", deleted, retention_days)
    return deleted
