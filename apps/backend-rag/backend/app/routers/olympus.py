"""Olympus DB Guardian — health and management endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger("olympus.router")

internal_router = APIRouter(prefix="/internal/olympus", tags=["olympus-internal"])


@internal_router.post("/pulse")
async def trigger_pulse(request: Request) -> dict[str, Any]:
    """Manually trigger a pulse cycle."""
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
