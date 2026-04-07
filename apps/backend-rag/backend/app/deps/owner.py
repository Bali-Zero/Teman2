"""Owner-only access dependency.

Only zero@balizero.com and antonellosiano@balizero.com (alias of zero)
are allowed. All other admins (asya, adit, etc.) receive 403.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException

from backend.app.deps.auth import get_current_user

logger = logging.getLogger(__name__)

OWNER_EMAILS: frozenset[str] = frozenset({
    "zero@balizero.com",
    "antonellosiano@balizero.com",
})


async def require_owner(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Gate an endpoint to owner-only access.

    Raises:
        HTTPException 403: if caller is not an owner
    """
    email = user.get("email")
    if email not in OWNER_EMAILS:
        logger.warning(
            "Owner-only access denied email=%s role=%s",
            email,
            user.get("role"),
        )
        raise HTTPException(
            status_code=403,
            detail="Owner access required",
        )
    return user
