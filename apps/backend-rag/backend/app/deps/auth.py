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

        # S03: Two-phase JWT expiry enforcement
        if settings.jwt_enforce_expiry:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        else:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )

        # S03-S3: Reject non-access tokens (e.g. refresh tokens)
        # Skip check if type claim absent (backward compat with pre-S03 tokens)
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_email = payload.get("email") or payload.get("sub")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

        user_ctx = {
            "email": user_email,
            "user_id": payload.get("user_id", user_email),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
        }

        # S03: Audit mode — flag expired tokens without rejecting
        if not settings.jwt_enforce_expiry:
            exp = payload.get("exp")
            if exp:
                from datetime import datetime, timezone

                if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                    logger.warning(
                        f"S03_AUDIT: Expired token used by {user_email} "
                        f"(jti={payload.get('jti', 'none')})"
                    )
                    user_ctx["_warn_expired"] = True

        # S03-S2: Token revocation check
        # Note: get_current_user is sync. Full async revocation check
        # runs in HybridAuthMiddleware (async context). This sync path
        # logs a warning if revocation is enabled but cannot check.
        if settings.enable_token_revocation:
            jti = payload.get("jti")
            if jti:
                logger.debug("S03-S2: Token jti=%s — revocation check deferred to middleware", jti)

        return user_ctx
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except HTTPException:
        raise
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
    Dependency that ensures the current user is a team member (not a client).

    Raises:
        HTTPException 403: If user is a client
    """
    if user.get("role") == "client":
        logger.warning(f"Access denied to client user: {user.get('email')}")
        raise HTTPException(
            status_code=403,
            detail="Access denied. This endpoint is only accessible to team members.",
        )
    return user
