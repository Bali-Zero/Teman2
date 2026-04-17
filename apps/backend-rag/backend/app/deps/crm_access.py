"""
CRM access control dependencies.

Centralizes RBAC checks as FastAPI dependencies so routers
don't repeat inline permission logic.
"""

import logging
from typing import Any

from fastapi import Depends, HTTPException

from backend.app.deps.auth import get_current_user
from backend.app.utils.crm_utils import (
    _practices_full_view_emails,
    can_view_all_practices,
    is_crm_admin,
    is_super_admin,
)

logger = logging.getLogger(__name__)


def _clients_full_view_emails() -> frozenset[str]:
    """Emails with full client list visibility — mirrors practices full view."""
    return _practices_full_view_emails()

__all__ = [
    "require_crm_admin",
    "require_super_admin",
    "get_crm_user_filter",
    "get_practices_user_filter",
    "can_view_all_clients",
]


def can_view_all_clients(user: dict) -> bool:
    """All authenticated team members can see the full client list.

    Client visibility is separated from ownership (assigned_to).
    Everyone sees all clients; assigned_to determines responsibility,
    notifications, and write permissions — not read access.

    Practices, channels, and omnichannel remain filtered by assigned_to.
    """
    if not user:
        return False
    return True


def require_crm_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """FastAPI dependency — raises 403 if user is not a CRM admin."""
    if not is_crm_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="CRM admin access required",
        )
    return current_user


def require_super_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """FastAPI dependency — raises 403 if user is not a super admin."""
    if not is_super_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Super admin access required",
        )
    return current_user


def get_crm_user_filter(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> str | None:
    """Return the user's email for filtering, or None if they can see everything.

    Usage in routers:
        assigned_filter = Depends(get_crm_user_filter)
        # assigned_filter is None → show all
        # assigned_filter is "user@email.com" → WHERE assigned_to = $N
    """
    if can_view_all_clients(current_user):
        return None
    return current_user.get("email", "").lower()


def get_practices_user_filter(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> str | None:
    """Return the user's email for practice filtering, or None for full view."""
    if can_view_all_practices(current_user):
        return None
    return current_user.get("email", "").lower()
