"""Authenticated late-incident resolution — POST /api/hr/my-late-incident/resolve.

The gate (spec §3.3) lets a logged-in worker explain an unexplained late arrival
WITHOUT the email token. This is the authenticated twin of the token form in
`hr_late_reply.py`: identity comes from the JWT (`get_current_user`), the target
incident is found by `email = current_user.email`, and the SAME state transition
is applied via the shared `next_state_for` helper (anti-drift, spec §4.2).

Scope is ALL pending dates, not just today (panel fix F2) — otherwise a worker
escapes the gate by waiting until tomorrow. Idempotent: if nothing is pending
(already resolved or never late), returns 200 with state="clear".

PII / Law 2: LOCAL Postgres only; the response is a small status dict (no rows).
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.hr.late_incident_resolver import next_state_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr", tags=["hr", "gate"])

_PENDING_STATES = ("AWAITING_REPLY", "REMINDER_SENT", "ESCALATED")


class ResolveBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/my-late-incident/resolve")
async def resolve_my_late_incident(
    body: ResolveBody,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Submit a reason for the logged-in user's oldest pending late incident.

    Returns:
        {"success": true, "state": "RESOLVED"|"RESOLVED_LATE"|"ESCALATED"}
        {"success": true, "state": "clear", "message": "no pending late incident"}
          when nothing is pending (idempotent no-op).

    The transition matches the email-token form exactly (shared helper). Resolves
    the OLDEST pending incident first (FIFO) so a backlog clears deterministically;
    the gate re-probes after each call so multiple pending dates drain one per
    submission.
    """
    email = (user.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=401, detail="no identity")

    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason required")

    async with pool.acquire() as conn:
        # Oldest pending incident for this user, ANY date (F2). FIFO drain.
        row = await conn.fetchrow(
            """
            SELECT id, state
              FROM attendance_late_incidents
             WHERE lower(email) = $1
               AND state = ANY($2::text[])
               AND reply_received_at IS NULL
             ORDER BY late_date ASC, created_at ASC
             LIMIT 1
            """,
            email,
            list(_PENDING_STATES),
        )

        if row is None:
            # Idempotent: nothing to resolve → already clear.
            return {"success": True, "state": "clear", "message": "no pending late incident"}

        next_state = next_state_for(row["state"])
        await conn.execute(
            """
            UPDATE attendance_late_incidents
               SET reply_received_at = NOW(),
                   reply_content     = $1,
                   state             = $2,
                   updated_at        = NOW()
             WHERE id = $3
            """,
            reason,
            next_state,
            row["id"],
        )

    logger.info(
        "resolve_my_late_incident: user=%s incident=%s -> state=%s",
        email, row["id"], next_state,
    )
    return {"success": True, "state": next_state}
