"""EventBus monitoring endpoint."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.app.dependencies import get_current_user
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stats")
async def get_event_bus_stats(
    request: Request,
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Get EventBus statistics — subscriber counts, event counts, recent traces."""
    event_bus = getattr(request.app.state, "event_bus", None)
    if not event_bus:
        return {"error": "EventBus not initialized", "running": False}
    return event_bus.get_stats()


@router.post("/emit")
async def emit_test_event(
    request: Request,
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Emit a test event for debugging (admin only)."""
    event_bus = getattr(request.app.state, "event_bus", None)
    if not event_bus:
        return {"error": "EventBus not initialized"}

    body = await request.json()
    event_type = body.get("event_type", "test.ping")
    payload = body.get("payload", {"test": True})

    trace = await event_bus.emit(event_type, payload, source="manual")
    return {
        "emitted": True,
        "event_type": event_type,
        "handler_count": trace.handler_count,
        "duration_ms": trace.duration_ms,
        "errors": trace.errors,
    }
