"""ack_outbox_event — manually mark a stuck outbox row as consumed.

Use case: an event was published but the handler crashed before
acknowledging. The row sits unconsumed in events_outbox forever (until
the prune action runs). This action marks it consumed without
re-dispatching, breaking the loop.

Idempotency: events_outbox.id is UNIQUE; the SQL has a guard
``WHERE id = $1 AND consumed_at IS NULL``, so re-execution is a no-op.

dry_run=True → returns whether the row would be acked, without writing.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)


@register_action("ack_outbox_event")
async def ack_outbox_event_action(
    proposal: Any,
    *,
    dry_run: bool = False,
    db_pool: Any = None,
) -> ActionResult:
    """Mark events_outbox row consumed.

    proposal.action_payload must contain:
        outbox_id (int)        — required
        reason     (str, opt)  — diagnostic note for audit

    db_pool is injected by the daemon (asyncpg.Pool). If absent, the
    action returns a structured failure rather than crashing.
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    outbox_id = payload.get("outbox_id")
    reason = str(payload.get("reason", "manual ack via FAD"))[:200]

    if outbox_id is None:
        return ActionResult(
            success=False,
            message="action_payload.outbox_id is required",
        )
    try:
        outbox_id_int = int(outbox_id)
    except (TypeError, ValueError):
        return ActionResult(
            success=False,
            message=f"outbox_id must be int, got {type(outbox_id).__name__}",
        )

    if db_pool is None:
        return ActionResult(
            success=False,
            message="db_pool not injected; daemon misconfigured",
        )

    if dry_run:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, channel, created_at, consumed_at
                  FROM events_outbox
                 WHERE id = $1
                """,
                outbox_id_int,
            )
        if row is None:
            return ActionResult(
                success=False,
                message=f"outbox_id {outbox_id_int} not found",
            )
        if row["consumed_at"] is not None:
            return ActionResult(
                success=True,
                message=f"DRY-RUN: outbox_id {outbox_id_int} already consumed",
                metadata={"already_consumed": True, "channel": row["channel"]},
            )
        return ActionResult(
            success=True,
            message=f"DRY-RUN: would ack outbox_id {outbox_id_int}",
            metadata={
                "channel": row["channel"],
                "age_seconds": (
                    None
                    if row["created_at"] is None
                    else (row["created_at"].timestamp() if hasattr(
                        row["created_at"], "timestamp"
                    ) else None)
                ),
            },
        )

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            UPDATE events_outbox
               SET consumed_at = NOW(),
                   consumer_id = $2
             WHERE id = $1
               AND consumed_at IS NULL
            RETURNING id, channel
            """,
            outbox_id_int,
            f"fad-ack:{reason}",
        )

    if result is None:
        return ActionResult(
            success=True,  # Idempotent: already consumed counts as success
            message=f"outbox_id {outbox_id_int} already consumed (no-op)",
            metadata={"already_consumed": True},
        )
    return ActionResult(
        success=True,
        message=f"acked outbox_id {outbox_id_int} (channel={result['channel']})",
        side_effects=(f"events_outbox.id={outbox_id_int}",),
        metadata={"channel": result["channel"]},
    )


__all__ = ["ack_outbox_event_action"]
