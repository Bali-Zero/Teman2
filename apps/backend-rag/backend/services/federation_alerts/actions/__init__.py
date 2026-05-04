"""Whitelist V2 actions for the Federation Alert Dispatcher.

V1 (4 actions) — idempotent maintenance ops on local resources.
V2 (4 new actions, this PR) — Codex 5.5 capabilities (OAuth Pro $200,
no API key). See registry.py for ALLOWED_L2 / HITL_ONLY routing.

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
    # Whitelist V2 — Codex 5.5 capabilities (OAuth Pro, no API key)
    codex_image_gen,
    codex_overnight_queue,
    codex_visual_dispatch,
    codex_xhigh_fix,
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
