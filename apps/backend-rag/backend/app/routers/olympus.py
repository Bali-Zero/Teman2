"""Olympus DB Guardian — health and management endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import get_current_user
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger("olympus.router")

internal_router = APIRouter(prefix="/internal/olympus", tags=["olympus-internal"])


def _require_pulse_admin(user: dict[str, Any]) -> None:
    """Gate manual pulse-trigger to admins. Raises 403 otherwise.

    ``trigger_pulse`` runs autonomous remediation actions against the DB —
    an authenticated team member is not a sufficient principal (Case OS R3).
    """
    if not is_crm_admin(user):
        raise HTTPException(status_code=403, detail="admin required")


@internal_router.post("/pulse")
async def trigger_pulse(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually trigger a pulse cycle."""
    _require_pulse_admin(current_user)
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return {"error": "Olympus not initialized"}
    actions = await olympus.run_pulse_once()
    return {
        "actions": len(actions),
        "successes": sum(1 for a in actions if a.outcome == "success"),
        "failures": sum(1 for a in actions if a.outcome == "failure"),
    }


@internal_router.get("/rules")
async def list_rules(request: Request) -> list[dict[str, Any]]:
    """List all active Olympus rules."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return []
    return [r.model_dump() for r in olympus.rules_engine.rules.values()]
