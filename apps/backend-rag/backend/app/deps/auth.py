"""
Authentication and authorization dependencies.

Provides JWT validation, user extraction, and RBAC guards.
No heavy service imports at module level — only jose, fastapi.security.
"""

import logging
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.app.utils.service_accounts import is_human_team_member, normalize_role
from backend.services.security.token_revocation import (
    RevocationStoreUnavailable,
    is_session_revoked_sync,
)

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication (shared singleton)
security = HTTPBearer(auto_error=False)

__all__ = [
    "get_current_user",
    "get_current_user_email",
    "get_current_user_optional",
    "require_team_member",
    "security",
]


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """
    Validate JWT token and return current user.

    Priority:
    1. Use request.state.user if set by HybridAuthMiddleware (cookie JWT auth)
    2. Fallback to validating Authorization header token (backward compatibility)

    Returns:
        dict: User information with keys: email, user_id, role, permissions

    Raises:
        HTTPException 401: If authentication fails
    """
    # Priority 1: Use user from middleware if available (cookie JWT auth)
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        return {
            "email": user.get("email"),
            "user_id": user.get("id") or user.get("user_id") or user.get("email"),
            "role": user.get("role", "user"),
            "permissions": user.get("permissions", []),
        }

    # Priority 2: Fallback to Authorization header token (backward compatibility)
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from backend.app.core.config import settings

        token = credentials.credentials

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True, "require_exp": True},
        )

        # S03-S3: Reject non-access tokens (e.g. refresh tokens)
        # Skip check if type claim absent (backward compat with pre-S03 tokens)
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_email = payload.get("email") or payload.get("sub")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

        if is_session_revoked_sync(payload):
            logger.warning("Rejected revoked JWT session")
            raise HTTPException(status_code=401, detail="Session revoked")

        return {
            "email": user_email,
            "user_id": payload.get("user_id", user_email),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
        }
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except HTTPException:
        raise
    except RevocationStoreUnavailable as e:
        logger.error("Authentication unavailable: session revocation cannot be checked")
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable",
        ) from e
    except Exception as e:
        logger.error("Authentication error: %s", e, exc_info=True)
        raise HTTPException(status_code=401, detail="Authentication failed") from e


def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any] | None:
    """
    Optional version of get_current_user that returns None instead of raising 401.
    """
    try:
        return get_current_user(request, credentials)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise
    except Exception as exc:
        # UU PDP audit: an unexpected exception in the optional auth path
        # still leaves the caller anonymous, but MUST be traceable.
        logger.warning(
            "auth.optional_user_failed",
            extra={"error_type": type(exc).__name__, "error": str(exc)},
            exc_info=False,
        )
        return None


def get_current_user_email(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> str:
    """
    Extract email from authenticated user.

    Returns:
        str: User's email address
    """
    return str(user["email"])


def require_team_member(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    Dependency that ensures the current user is a real person on the team.

    Neither clients nor unattended service accounts (e.g. the login-healthcheck
    probe, role "monitoring") qualify — this gate grants team-level authority
    (e33 case creation, CRM intelligence mutations), and "not a client" is not
    the same question as "is a colleague". See service_accounts.py.

    Raises:
        HTTPException 403: If user is a client or a service account
    """
    if not is_human_team_member(user.get("role")):
        # The role is a job title or a token, never PII; logging it is what
        # makes an allow-list gap visible before a colleague reports a lockout.
        logger.warning(
            "Access denied to non-team account",
            extra={"role": normalize_role(user.get("role")) or "<empty>"},
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied. This endpoint is only accessible to team members.",
        )
    return user
