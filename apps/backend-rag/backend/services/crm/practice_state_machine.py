"""
Practice State Machine — Enforces valid status transitions.

States: inquiry → waiting_documents → sending_invoice → on_process → completed
        Any state → cancelled (admin only)

Created: 2026-04-06 — CRM Solidification Blocco A
"""

import logging
from typing import Any

from backend.app.utils.crm_utils import can_view_all_practices

logger = logging.getLogger(__name__)


# Valid forward transitions (from_state → set of allowed to_states)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "inquiry": {"waiting_documents", "cancelled"},
    "waiting_documents": {"sending_invoice", "inquiry", "cancelled"},
    "sending_invoice": {"on_process", "waiting_documents", "cancelled"},
    "on_process": {"completed", "sending_invoice", "cancelled"},
    "completed": {"cancelled"},  # Can only cancel after completion
    "cancelled": {"inquiry"},  # Can reopen a cancelled practice
}

# Transitions that require admin role
ADMIN_ONLY_TRANSITIONS: set[tuple[str, str]] = {
    ("completed", "cancelled"),
    ("cancelled", "inquiry"),
}

# All valid states
ALL_STATES = frozenset(VALID_TRANSITIONS.keys())


class InvalidTransitionError(Exception):
    """Raised when a practice status transition is not allowed."""

    def __init__(self, from_state: str, to_state: str, reason: str = "") -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        msg = f"Invalid transition: {from_state} → {to_state}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


def validate_transition(
    from_state: str,
    to_state: str,
    user: dict[str, Any] | None = None,
) -> bool:
    """
    Validate a practice status transition.

    Args:
        from_state: Current practice status
        to_state: Desired new status
        user: Current user dict (for admin-only checks)

    Returns:
        True if transition is valid

    Raises:
        InvalidTransitionError: If transition is not allowed
    """
    # Same state = no-op, always allowed
    if from_state == to_state:
        return True

    # Check state exists
    if from_state not in ALL_STATES:
        raise InvalidTransitionError(from_state, to_state, f"unknown current state '{from_state}'")
    if to_state not in ALL_STATES:
        raise InvalidTransitionError(from_state, to_state, f"unknown target state '{to_state}'")

    # Check transition is in the allowed set
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise InvalidTransitionError(
            from_state,
            to_state,
            f"allowed transitions from '{from_state}': {sorted(allowed)}",
        )

    # Check admin-only transitions
    if (from_state, to_state) in ADMIN_ONLY_TRANSITIONS:
        if user is None:
            raise InvalidTransitionError(from_state, to_state, "requires admin role")
        if not can_view_all_practices(user):
            raise InvalidTransitionError(
                from_state,
                to_state,
                f"Admin-only transition: {from_state} -> {to_state}. "
                f"Only admins can perform this action.",
            )

    logger.debug(f"State transition validated: {from_state} → {to_state}")
    return True


# Legacy state mapping for migration
LEGACY_STATE_MAP: dict[str, str] = {
    "quotation_sent": "sending_invoice",
    "payment_pending": "sending_invoice",
    "waiting_payment": "sending_invoice",
    "in_progress": "on_process",
    "submitted_to_gov": "on_process",
    "approved": "on_process",
}


def normalize_state(state: str) -> str:
    """Map legacy state names to current 5-state model."""
    return LEGACY_STATE_MAP.get(state, state)
