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
    PRACTICES_FULL_VIEW_EMAILS,
    can_view_all_practices,
    is_crm_admin,
    is_super_admin,
)

logger = logging.getLogger(__name__)

# Emails with full client list visibility (mirrors PRACTICES_FULL_VIEW_EMAILS)
CLIENTS_FULL_VIEW_EMAILS: set[str] = PRACTICES_FULL_VIEW_EMAILS

__all__ = [
    "require_crm_admin",
    "require_super_admin",
    "get_crm_user_filter",
    "get_practices_user_filter",
    "can_view_all_clients",
]


def can_view_all_clients(user: dict) -> bool:
    """Check if a user can see ALL clients (admin, super admin, accounting).

    Mirror of can_view_all_practices — same email/role whitelist.
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    role = user.get("role", "").lower()

    if email in CLIENTS_FULL_VIEW_EMAILS:
        return True

    if role in ("admin", "board member", "ceo", "founder"):
        return True

    return False


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
