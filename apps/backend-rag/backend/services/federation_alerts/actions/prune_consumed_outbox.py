"""prune_consumed_outbox — delete already-consumed events_outbox rows.

Bounded scope:
    * Only rows WHERE consumed_at IS NOT NULL AND consumed_at < cutoff
    * Cutoff defaults to NOW() - INTERVAL '30 days' (configurable)
    * Single DELETE in a transaction, batch <= 5000 rows
    * Returns the number deleted (audit-friendly)

Per cicatrix scar 2026-04-29 P0-2 fase 2: the events_outbox table
grows unbounded post-PR-#342 because the pruning cron was deferred to
phase 3. This action is the Phase-3 manual hook: invoked from a FAD
proposal (typically on its own schedule, not in response to alerts).

dry_run=True → counts the rows it WOULD delete, without removing.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_BATCH_SIZE = 5000


@register_action("prune_consumed_outbox")
async def prune_consumed_outbox_action(
    proposal: Any,
    *,
    dry_run: bool = False,
    db_pool: Any = None,
) -> ActionResult:
    """Delete events_outbox rows where consumed_at < NOW() - max_age_days.

    proposal.action_payload may set:
        max_age_days  (int, default 30, capped at 1..365)
        batch_size    (int, default 5000, capped at 1..50_000)
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    max_age_days = int(payload.get("max_age_days", DEFAULT_MAX_AGE_DAYS))
    batch_size = int(payload.get("batch_size", DEFAULT_BATCH_SIZE))
    max_age_days = max(1, min(max_age_days, 365))
    batch_size = max(1, min(batch_size, 50_000))

    if db_pool is None:
        return ActionResult(
            success=False,
            message="db_pool not injected; daemon misconfigured",
        )

    if dry_run:
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT count(*)
                  FROM (
                      SELECT id
                        FROM events_outbox
                       WHERE consumed_at IS NOT NULL
                         AND consumed_at < NOW() - ($1 || ' days')::interval
                       ORDER BY consumed_at
                       LIMIT $2
                  ) AS sub
                """,
                str(max_age_days),
                batch_size,
            )
        return ActionResult(
            success=True,
            message=(
                f"DRY-RUN: would prune {count} rows older than "
                f"{max_age_days}d (batch_size={batch_size})"
            ),
            metadata={"would_prune_count": int(count or 0)},
        )

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            deleted = await conn.fetchval(
                """
                WITH del AS (
                    DELETE FROM events_outbox
                     WHERE id IN (
                         SELECT id
                           FROM events_outbox
                          WHERE consumed_at IS NOT NULL
                            AND consumed_at <
                                NOW() - ($1 || ' days')::interval
                          ORDER BY consumed_at
                          LIMIT $2
                     )
                    RETURNING id
                )
                SELECT count(*) FROM del
                """,
                str(max_age_days),
                batch_size,
            )

    deleted_int = int(deleted or 0)
    return ActionResult(
        success=True,
        message=(
            f"pruned {deleted_int} events_outbox rows older than "
            f"{max_age_days}d"
        ),
        side_effects=(f"events_outbox: -{deleted_int} rows",),
        metadata={
            "deleted_count": deleted_int,
            "max_age_days": max_age_days,
            "batch_size": batch_size,
        },
    )


__all__ = ["prune_consumed_outbox_action"]
