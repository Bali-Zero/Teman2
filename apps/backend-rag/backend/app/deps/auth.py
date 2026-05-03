"""
Authentication and authorization dependencies.

Provides JWT validation, user extraction, and RBAC guards.
No heavy service imports at module level — only jose, fastapi.security.
"""

import logging
from typing import Annotated, Any

import asyncpg
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.app.deps.database import get_database_pool

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication (shared singleton)
security = HTTPBearer(auto_error=False)

__all__ = [
    "security",
    "get_current_user",
    "get_current_user_optional",
    "get_current_user_email",
    "require_team_member",
    "get_current_portal_client",
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
                token, settings.jwt_secret_key, algorithms=["HS256"],
                options={"verify_exp": True},
            )
        else:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=["HS256"],
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
                logger.debug(
                    f"S03-S2: Token jti={jti} — revocation check deferred to middleware"
                )

        return user_ctx
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
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


# Superusers allowed to impersonate any client via ?as_client=<id>.
# HIGH-7 (audit 2026-04-18): centralised into settings.admin_emails_set.
# Use the getter below to pick up ADMIN_EMAILS env-var changes without
# module reload. The portal router uses the same source (see
# backend/app/routers/portal.py:_superuser_emails).
def _superuser_emails() -> frozenset[str]:
    from backend.app.core.config import settings

    return settings.admin_emails_set


async def get_current_portal_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get current authenticated client from JWT token for Portal endpoints.

    Validates that:
    1. User has valid JWT token (set by middleware)
    2. User role is 'client' (bypassed for superusers)
    3. User has a linked client profile in the database
       (bypassed for superusers using ?as_client=<id>)

    Superuser impersonation mirrors portal.get_current_client — see that
    function for the full rationale. Audit entries are written from the
    portal.py code path; this dependency is used only by portal_visa and
    portal_taxes, both of which are read-only data fetches.

    Returns:
        dict: {id, email, full_name, impersonating (bool)}
    """
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = request.state.user
    user_email = (user.get("email") or "").lower()
    is_superuser = user_email in _superuser_emails()

    # ---- Superuser impersonation path ----
    if is_superuser:
        as_client_raw = request.query_params.get("as_client")
        if as_client_raw is None:
            async with db_pool.acquire() as conn:
                own = await conn.fetchrow(
                    "SELECT id, email, full_name FROM clients WHERE LOWER(email) = LOWER($1)",
                    user_email,
                )
            if own:
                return {**dict(own), "impersonating": False}
            raise HTTPException(
                status_code=422,
                detail="Superuser: select a client via ?as_client=<id>",
            )

        try:
            as_client_id = int(as_client_raw)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="as_client must be an integer",
            ) from e

        async with db_pool.acquire() as conn:
            target = await conn.fetchrow(
                "SELECT id, email, full_name FROM clients WHERE id = $1",
                as_client_id,
            )
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Client {as_client_id} not found",
            )
        return {**dict(target), "impersonating": True}

    # ---- Normal client path ----
    if user.get("role") != "client":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only accessible to clients",
        )

    async with db_pool.acquire() as conn:
        client_row = await conn.fetchrow(
            """
            SELECT c.id, c.email, c.full_name
            FROM clients c
            JOIN user_profiles up ON up.linked_client_id = c.id
            WHERE up.id = $1 AND up.role = 'client'
            """,
            user.get("user_id"),
        )

        if not client_row:
            logger.warning(
                f"Portal client lookup failed for user_id={user.get('user_id')} email={user.get('email')}",
            )
            raise HTTPException(
                status_code=404,
                detail="Client profile not found. Please contact support.",
            )

        return {**dict(client_row), "impersonating": False}
