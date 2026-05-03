"""
Admin Self-Healing Router.

Exposes the stats snapshot of the in-process self-healing orchestrator:
check-level success/failure counts, last error, recovery duration, and
circuit-breaker state per check. Admin API key required.

The orchestrator is registered by the autonomous_scheduler via
`backend.self_healing.set_active_agent`; this router looks it up with
`get_active_agent` and returns `{"configured": False}` when no agent has
been wired in the current process (e.g., a bare main_api stack).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.routers.debug import verify_debug_access
from backend.app.utils.logging_utils import get_logger
from backend.self_healing import get_active_agent

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/self-healing", tags=["admin-self-healing"])


@router.get("/stats")
async def get_self_healing_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Return the current snapshot: uptime, per-check stats
    (total_runs / total_success / total_failure / last_error /
    last_recovery_duration_seconds), per-action stats, and per-check
    circuit-breaker state.
    """
    agent = get_active_agent()
    if agent is None:
        return {"configured": False, "reason": "self_healing_agent not registered"}

    orchestrator = getattr(agent, "orchestrator", None)
    if orchestrator is None:
        return {"configured": False, "reason": "agent.orchestrator unavailable"}

    return {
        "configured": True,
        "service": getattr(agent, "service_name", "unknown"),
        **orchestrator.get_stats(),
    }
