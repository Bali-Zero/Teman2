"""quarantine_alert — suppress a duplicate/noisy proposal.

Pure DB state change on the dispatcher's own table. Sets
status='quarantined' on the target proposal so the daemon stops
re-dispatching it. Does NOT disable the upstream producer.

Use case: a misconfigured cron emits the same alert hundreds of times
per hour. We quarantine the proposal so Telegram doesn't get spammed,
without touching the producer (the producer's own circuit breaker —
or human action — is the right tool to disable it).

Idempotency: federation_alert_proposals.quarantine_token is UNIQUE.
The token is derived from (proposal_id, reason_code) so re-running
with the same reason is a no-op.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.services.federation_alerts.actions.registry import (
    ActionResult,
    register_action,
)

logger = logging.getLogger(__name__)


def _quarantine_token(proposal_id: str, reason_code: str) -> str:
    raw = f"quarantine:v1:{proposal_id}:{reason_code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@register_action("quarantine_alert")
async def quarantine_alert_action(
    proposal: Any,
    *,
    dry_run: bool = False,
    db_pool: Any = None,
) -> ActionResult:
    """Mark a proposal quarantined.

    proposal.action_payload must contain:
        target_proposal_id (str)  — the proposal to quarantine
        reason_code        (str)  — short stable code (e.g. "duplicate_fingerprint")
        reason_text        (str, optional)  — human-readable detail
    """
    payload = getattr(proposal, "action_payload", {}) or {}
    target_id = payload.get("target_proposal_id") or getattr(
        proposal, "proposal_id", None
    )
    reason_code = str(payload.get("reason_code", "unspecified"))[:64]
    reason_text = str(payload.get("reason_text", reason_code))[:500]

    if not target_id:
        return ActionResult(
            success=False,
            message="action_payload.target_proposal_id required",
        )
    if db_pool is None:
        return ActionResult(
            success=False,
            message="db_pool not injected; daemon misconfigured",
        )

    token = _quarantine_token(target_id, reason_code)

    if dry_run:
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT proposal_id, status, quarantined_at
                  FROM federation_alert_proposals
                 WHERE proposal_id = $1
                """,
                target_id,
            )
        if existing is None:
            return ActionResult(
                success=False,
                message=f"target proposal {target_id} not found",
            )
        if existing["status"] == "quarantined":
            return ActionResult(
                success=True,
                message=f"DRY-RUN: {target_id} already quarantined",
                metadata={"already_quarantined": True},
            )
        return ActionResult(
            success=True,
            message=f"DRY-RUN: would quarantine {target_id} ({reason_code})",
            metadata={"current_status": existing["status"], "token": token},
        )

    async with db_pool.acquire() as conn:
        # Block transitioning a terminal status (matches DB CHECK semantics).
        current = await conn.fetchrow(
            "SELECT status FROM federation_alert_proposals WHERE proposal_id = $1",
            target_id,
        )
        if current is None:
            return ActionResult(
                success=False,
                message=f"target proposal {target_id} not found",
            )
        if current["status"] in ("completed", "failed", "duplicate"):
            return ActionResult(
                success=False,
                message=(
                    f"cannot quarantine terminal status {current['status']}"
                ),
            )

        result = await conn.fetchrow(
            """
            UPDATE federation_alert_proposals
               SET status = 'quarantined',
                   quarantine_token = $2,
                   quarantine_reason = $3,
                   quarantined_at = NOW(),
                   completed_at = NOW(),
                   updated_at = NOW()
             WHERE proposal_id = $1
               AND status <> 'quarantined'
             RETURNING proposal_id, status
            """,
            target_id, token, reason_text,
        )

    if result is None:
        return ActionResult(
            success=True,  # Already quarantined → idempotent success
            message=f"{target_id} already quarantined (no-op)",
            metadata={"already_quarantined": True, "token": token},
        )
    return ActionResult(
        success=True,
        message=f"quarantined {target_id} (reason={reason_code})",
        side_effects=(f"federation_alert_proposals.proposal_id={target_id}",),
        metadata={"token": token, "reason_code": reason_code},
    )


__all__ = ["quarantine_alert_action"]
