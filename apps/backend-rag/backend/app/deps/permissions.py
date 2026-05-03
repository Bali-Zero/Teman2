"""
Permission-based authorization dependencies (S03 Sprint 3).

Provides fine-grained permission checks for API key scoped access
and security-sensitive endpoints (e.g., breach notification).
"""

import logging
from typing import Any

from fastapi import Depends, HTTPException

from backend.app.deps.auth import get_current_user

logger = logging.getLogger(__name__)


def check_permission(user: dict[str, Any], required: str) -> bool:
    """
    Check if user has a specific permission.

    Admin role always has all permissions.
    Wildcard '*' in permissions grants all.
    """
    if user.get("role") == "admin":
        return True
    permissions = user.get("permissions", [])
    if "*" in permissions:
        return True
    return required in permissions


def require_permission(required: str) -> Any:
    """
    FastAPI dependency factory for permission-gated endpoints.

    Usage:
        @router.post("/breach-notify")
        async def notify(user=Depends(require_permission("security.breach_notify"))):
            ...
    """
    def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not check_permission(user, required):
            logger.warning(
                f"S03: Permission denied — user={user.get('email')} "
                f"required={required} has={user.get('permissions', [])}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission required: {required}",
            )
        return user
    return _check
