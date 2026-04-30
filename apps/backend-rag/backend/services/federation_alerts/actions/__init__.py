"""Whitelist V1 actions for the Federation Alert Dispatcher.

Per spec: only 4 actions are safe enough for L2 autonomous in production
mode. Two patterns are deliberately BLOCKED or HITL_ONLY (see registry).

Pattern (adapted from Robusta's @action decorator under MIT, see:
https://github.com/robusta-dev/robusta):

    @register_action(
        name="cleanup_log",
        risk_level="L2",
        idempotency_template="cleanup_log:v1:{path}:{age_bucket}:{size_bucket}",
    )
    async def cleanup_log(proposal: ProposalRow, dry_run: bool) -> ActionResult:
        ...
"""
from __future__ import annotations

# Importing the action modules registers them via @register_action decorator
from backend.services.federation_alerts.actions import (  # noqa: F401
    ack_outbox_event,
    cleanup_log,
    prune_consumed_outbox,
    quarantine_alert,
)
from backend.services.federation_alerts.actions.registry import (
    ActionPolicy,
    ActionResult,
    classify_action,
    get_action,
    list_actions,
)

__all__ = [
    "ActionPolicy",
    "ActionResult",
    "classify_action",
    "get_action",
    "list_actions",
]
