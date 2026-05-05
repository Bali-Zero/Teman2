"""Action registry for FAD whitelist V1.

Pattern adapted from Robusta's @action (MIT). One module per action,
registered via @register_action at import time.

Safety policy machinery (B3+B4):
    BLOCKED_ACTIONS — never executed, even with manual approval.
    HITL_ONLY_ACTIONS — must require Telegram approval, regardless of mode.
    ALLOWED_L2_ACTIONS — daemon may execute autonomously in production mode.

The classify_action() function is the single source of truth for what
runs autonomously. Daemon code must never short-circuit it.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Safety policy — keep these in sync with RequestedAction enum in models.py.
BLOCKED_ACTIONS: frozenset[str] = frozenset({
    # P0-3 threat model unresolved (51/54 plist corruption 2026-04-29).
    "cleanup_zombie_plist",
})

HITL_ONLY_ACTIONS: frozenset[str] = frozenset({
    # Organism restart loop amplification risk — Telegram approval mandatory.
    "restart_agent",
    # Codex 5.5 deep agentic edit — broad blast radius, approval mandatory.
    "codex_xhigh_fix",
    # Codex image gen — public-facing, editorial review gate.
    "codex_image_gen",
    # Codex visual dispatch (15 assets) — public-facing bundle, editorial gate.
    "codex_visual_dispatch",
})

ALLOWED_L2_ACTIONS: frozenset[str] = frozenset({
    "cleanup_log",
    "ack_outbox_event",
    "quarantine_alert",
    "prune_consumed_outbox",
    # Whitelist V2: enqueue is non-destructive (queue write only; runner
    # processes at 22:00 with its own safeguards: 8h timeout, sandbox
    # workspace-write, branch-isolated, no auto-merge).
    "codex_overnight_queue",
})


@dataclass(frozen=True)
class ActionPolicy:
    """Routing decision for an inbound action request."""

    blocked: bool
    requires_approval: bool
    reason: str | None = None


def classify_action(action: str) -> ActionPolicy:
    """Return the safety policy for an action name.

    Daemon contract:
        - if blocked: never execute, mark proposal quarantined.
        - if requires_approval: route to Telegram even in production.
        - otherwise: execute autonomously (mode permitting).
    """
    if action in BLOCKED_ACTIONS:
        return ActionPolicy(
            blocked=True,
            requires_approval=False,
            reason=f"{action} is BLOCKED (V1 safety policy)",
        )
    if action in HITL_ONLY_ACTIONS:
        return ActionPolicy(
            blocked=False,
            requires_approval=True,
            reason=f"{action} requires human approval",
        )
    if action in ALLOWED_L2_ACTIONS:
        return ActionPolicy(blocked=False, requires_approval=False)
    return ActionPolicy(
        blocked=True,
        requires_approval=False,
        reason=f"unknown action: {action}",
    )


@dataclass(frozen=True)
class ActionResult:
    """Outcome of executing one action.

    Used by both dry-run and production paths. ``side_effects`` lists
    the changes (paths deleted, rows updated, etc.) for audit.
    """

    success: bool
    message: str
    side_effects: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

ActionFn = Callable[..., Awaitable[ActionResult]]
_REGISTRY: dict[str, ActionFn] = {}


def register_action(name: str) -> Callable[[ActionFn], ActionFn]:
    """Decorator: register an action by name (matches RequestedAction enum)."""

    def decorator(fn: ActionFn) -> ActionFn:
        if name in _REGISTRY:
            logger.warning("action %s already registered; overwriting", name)
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_action(name: str) -> ActionFn | None:
    return _REGISTRY.get(name)


def list_actions() -> list[str]:
    return sorted(_REGISTRY.keys())


__all__ = [
    "ActionPolicy",
    "ActionResult",
    "BLOCKED_ACTIONS",
    "HITL_ONLY_ACTIONS",
    "ALLOWED_L2_ACTIONS",
    "classify_action",
    "register_action",
    "get_action",
    "list_actions",
]
