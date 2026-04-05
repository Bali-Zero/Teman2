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
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

        user_email = payload.get("email") or payload.get("sub")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

        return {
            "email": user_email,
            "user_id": payload.get("user_id", user_email),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
        }
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
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
    except Exception:
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


async def get_current_portal_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get current authenticated client from JWT token for Portal endpoints.

    Validates that:
    1. User has valid JWT token (set by middleware)
    2. User role is 'client' (not team member)
    3. User has a linked client profile in the database

    Returns:
        dict: Client information with keys: id, email, full_name

    Raises:
        HTTPException 401: If no valid JWT token present
        HTTPException 403: If user role is not 'client'
        HTTPException 404: If client profile not found in database
    """
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = request.state.user

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

        return dict(client_row)
