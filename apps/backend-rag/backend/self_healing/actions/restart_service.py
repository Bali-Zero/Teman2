"""
Service-restart action. Placeholder that returns False — a real restart on
Fly.io is driven by the supervisor (process exit) and requires orchestration
outside this agent's blast radius.
"""

from __future__ import annotations

from backend.self_healing.actions.base import ActionResult


class RestartServiceAction:
    name = "restart_service"
    target_check = "api"

    async def run(self) -> ActionResult:
        # Intentional no-op: autonomous process kill inside a running service
        # is a larger design question (who supervises the supervisor?). We
        # keep the slot so ops can escalate to a human via reporter.py.
        return ActionResult(
            success=False,
            detail="restart is manual — escalation logged by reporter",
        )
