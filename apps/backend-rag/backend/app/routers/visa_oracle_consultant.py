"""POST /api/visa-oracle/consultant-assignment — emit the frozen C3 event.

Public, unauthenticated (matches the anonymous wizard — the whole point of
C3 is that it must be emittable before a client identity exists,
``docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md`` C3). This is
the ``ConsultantAssignmentEvent`` "shortest jump" wiring: the frontend's
"Talk to a consultant" control (today: ``ConsentHandoff.tsx`` on the verdict
screen) calls this endpoint at the moment a visitor invokes it, and the
durable row this writes IS the CRM receiving a signal.

The request body is intentionally NOT the frozen event itself.
``ConsultantAssignmentEvent.requested_at`` is server-stamped, never
client-supplied — trusting a client clock for an audit timestamp is not
this contract's job, and letting the client set it would open a channel
this event does not need. Every other field maps straight through and gets
re-validated by C3's own guards (closed types, ``extra="forbid"``, the Law 2
PII-shaped-key check) when ``ConsultantAssignmentEvent`` is constructed
below — free defense-in-depth, not duplicated by hand here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

from backend.app.dependencies import get_database_pool
from backend.services.visa_engine.consultant_assignment import (
    ConsultantAssignmentEvent,
    EventLocale,
    OriginScreen,
    ServiceTier,
)
from backend.services.visa_engine.consultant_assignment_service import (
    notify_consultant_assignment_request,
    record_consultant_assignment_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visa-oracle", tags=["visa-oracle-consultant"])


class ConsultantAssignmentRequestBody(BaseModel):
    """Client-supplied subset of C3 — everything except ``requested_at``."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: UUID
    client_id: UUID | None = None
    origin_screen: OriginScreen
    tier: ServiceTier
    product_version_id: UUID | None = None
    locale: EventLocale


class ConsultantAssignmentAccepted(BaseModel):
    accepted: bool
    request_id: str


@router.post(
    "/consultant-assignment",
    operation_id="requestVisaOracleConsultantAssignment",
    response_model=ConsultantAssignmentAccepted,
    status_code=202,
)
async def request_consultant_assignment(
    body: ConsultantAssignmentRequestBody,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConsultantAssignmentAccepted:
    try:
        event = ConsultantAssignmentEvent(
            **body.model_dump(),
            requested_at=datetime.now(timezone.utc),
        )
    except ValidationError:
        # C3's own guards (closed types, extra=forbid, Law 2 PII-key check)
        # rejected a body that already passed FastAPI's own schema check —
        # should not happen for a legitimate caller; never echo internals.
        logger.warning("consultant_assignment request failed C3 re-validation", exc_info=True)
        raise HTTPException(
            status_code=400, detail="Invalid consultant assignment request"
        ) from None

    try:
        request_id = await record_consultant_assignment_request(event, db_pool)
    except Exception:
        # The durable write IS the deliverable ("CRM receives a signal") —
        # unlike the notify step below, a failure here is a real error.
        logger.exception("consultant_assignment_request persistence failed")
        raise HTTPException(
            status_code=500, detail="Could not record consultant assignment request"
        ) from None

    # Best-effort amplifier on top of the already-durable row above.
    # notify_consultant_assignment_request never raises (see its own
    # docstring) — awaited directly rather than fired-and-forgotten via
    # asyncio.create_task so a slow/failing send is still bounded by this
    # request's own timeout instead of leaking an untracked background task.
    await notify_consultant_assignment_request(event, request_id)

    return ConsultantAssignmentAccepted(accepted=True, request_id=str(request_id))
