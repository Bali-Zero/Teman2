"""Observed-shell tier — HTTP endpoint for shell-side automations.

Sprint 1 PR-1.2 — wires the cell-core ``ObservedShellBus`` (Sprint 0
Track C2, migration 151) to the outside world via a single HTTP POST so
that shell-only callers (LaunchAgents, cron-agent-python strategies, bash
wrappers) can record observability events without importing cell-core.

The endpoint is internal (X-API-Key authenticated, NOT in
``PUBLIC_ENDPOINTS``). The cell never accepts arbitrary observability
emissions from the public internet — Symbiosis Law 5 (Zero ultima
istanza) at the network layer.

Spec: ``docs/cell-core/observed-shell-tier.md`` § "Bash (LaunchAgent /
launchd cron jobs)".

Cicatrix reference: Sprint 1.B 2026-05-02 (3-PR hotfix chain) — the
endpoint is added in lockstep across 5 files (this router, manifest,
two ``router_registration.py`` include functions, and the new contract
test). NOT added to ``PUBLIC_ENDPOINTS`` because the X-API-Key gate is
the right authorisation surface for service-to-service traffic.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.services.events.observed_shell import VALID_STATUSES, ObservedShellBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observed-shell", tags=["observability", "internal"])


class EmitRequest(BaseModel):
    """Request body for the observed-shell emit endpoint.

    Mirrors ``ObservedShellBus.emit`` keyword arguments. ``payload`` and
    ``trace_id`` are optional; status MUST be one of ``VALID_STATUSES``.
    """

    automation_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Slug for the automation, e.g. 'translate.hourly'",
    )
    status: str = Field(
        ...,
        description="One of: ok | error | warning | skipped",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Free-form structured payload — JSONB column",
    )
    trace_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional upstream trace ID for cross-system correlation",
    )


class EmitResponse(BaseModel):
    """Successful emit response. The endpoint never returns DB row IDs —
    callers don't need them, and exposing them would couple the schema."""

    accepted: bool = True
    automation_name: str
    status: str


@router.post(
    "/emit",
    response_model=EmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record an observed-shell event",
)
async def emit_observed_shell_event(
    body: EmitRequest,
    request: Request,
    _api_key_verified=Depends(verify_internal_api_key),
) -> EmitResponse:
    """Record one observed-shell event from a shell-only caller.

    Returns 202 Accepted (NOT 201) because the underlying ``ObservedShellBus``
    is best-effort: the row may also land in the JSONL fallback if the DB
    pool is unavailable, in which case the cell hasn't actually persisted
    anything to PG yet but the trace is preserved.

    Status validation: out-of-allowlist values are coerced to ``error`` by
    ``ObservedShellBus.emit`` itself; we surface that explicitly via 422
    here so misconfigured callers fail loud at integration time rather
    than silently flipping their status field server-side.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"status must be one of {sorted(VALID_STATUSES)!r}; "
                f"got {body.status!r}"
            ),
        )

    pool = getattr(request.app.state, "db_pool", None)
    bus = ObservedShellBus(pool)
    await bus.emit(
        automation_name=body.automation_name,
        status=body.status,
        payload=body.payload,
        trace_id=body.trace_id,
    )

    logger.info(
        "observed-shell emit: automation=%s status=%s trace_id=%s",
        body.automation_name,
        body.status,
        body.trace_id,
    )
    return EmitResponse(
        accepted=True,
        automation_name=body.automation_name,
        status=body.status,
    )


__all__ = ["router"]
