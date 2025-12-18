"""
Authentication Decorators
Provides decorators for endpoint security classification and access control
"""

import logging
from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def require_auth(auth_type: str = "any", permissions: list = None):
    """
    Authentication decorator for endpoint protection

    Args:
        auth_type: Type of authentication required ("api_key", "jwt", "any")
        permissions: List of required permissions (for API key roles)

    Usage:
        @require_auth("api_key", permissions=["*"])
        async def protected_endpoint(request: Request):
            return {"message": "Access granted"}
    """
    if permissions is None:
        permissions = []

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check if user context exists in request state (injected by middleware)
            if not hasattr(request.state, "user") or not request.state.user:
                logger.warning(f"Authentication required for {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
                )

            user_context = request.state.user
            auth_method = getattr(user_context, "auth_method", "unknown")

            # Validate authentication type
            if auth_type == "api_key" and auth_method != "api_key":
                logger.warning(
                    f"API Key authentication required for {request.url.path}, got {auth_method}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key authentication required",
                )

            if auth_type == "jwt" and auth_method != "jwt":
                logger.warning(
                    f"JWT authentication required for {request.url.path}, got {auth_method}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT authentication required"
                )

            # Check permissions (for API key users)
            if permissions and auth_method == "api_key":
                user_permissions = getattr(user_context, "permissions", [])
                if not all(perm in user_permissions for perm in permissions if perm != "*"):
                    logger.warning(
                        f"Insufficient permissions for {request.url.path}: {user_permissions}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
                    )

            logger.debug(
                f"Access granted to {request.url.path} for user: {user_context.get('role', 'unknown')}"
            )
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def public_endpoint(func: Callable) -> Callable:
    """
    Decorator for public endpoints that don't require authentication
    Simply passes through without authentication checks
    """

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        logger.debug(f"Public endpoint accessed: {request.url.path}")
        return await func(request, *args, **kwargs)

    return wrapper


def optional_auth(func: Callable) -> Callable:
    """
    Decorator for endpoints that work with or without authentication
    If user is authenticated, provides user context; otherwise continues as anonymous
    """

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user_context = getattr(request.state, "user", None)
        auth_method = getattr(user_context, "auth_method", None) if user_context else "public"

        logger.debug(f"Optional auth endpoint accessed: {request.url.path} (auth: {auth_method})")
        return await func(request, *args, **kwargs)

    return wrapper


def role_required(allowed_roles: list):
    """
    Decorator to restrict access by user roles

    Args:
        allowed_roles: List of allowed roles (e.g., ["admin", "user"])

    Usage:
        @role_required(["admin"])
        async def admin_only_endpoint(request: Request):
            return {"message": "Admin access granted"}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not hasattr(request.state, "user") or not request.state.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
                )

            user_context = request.state.user
            user_role = user_context.get("role", "public")

            if user_role not in allowed_roles:
                logger.warning(f"Access denied for role '{user_role}' to {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}",
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def api_key_required(permissions: list = None):
    """
    Decorator specifically for API Key authentication

    Args:
        permissions: List of required permissions

    Usage:
        @api_key_required(permissions=["*"])
        async def api_key_endpoint(request: Request):
            return {"message": "API Key access granted"}
    """
    return require_auth(auth_type="api_key", permissions=permissions)


def jwt_required(_func: Callable) -> Callable:
    """
    Decorator specifically for JWT authentication

    Usage:
        @jwt_required
        async def jwt_endpoint(request: Request):
            return {"message": "JWT access granted"}
    """
    return require_auth(auth_type="jwt")


class AuthException(Exception):
    """Custom authentication exception"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def handle_auth_error(request: Request, exc: Exception):
    """
    Global exception handler for authentication errors
    """
    if isinstance(exc, AuthException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "path": str(request.url)},
        )
    else:
        # Generic error handler
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Authentication error", "path": str(request.url)},
        )


# Endpoint security classification constants
class SecurityLevel:
    """Constants for endpoint security classification"""

    PUBLIC = "public"
    API_KEY = "api_key"
    JWT = "jwt"
    HYBRID = "hybrid"
    ADMIN_ONLY = "admin_only"


# Endpoint classification mapping
ENDPOINT_CLASSIFICATION = {
    # Public endpoints (no auth required)
    "public": [
        "/",
        "/health",
        "/api/health",
        "/healthz",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/csrf-token",
        "/api/search/health",
    ],
    # API Key endpoints (can use API key auth)
    "api_key": [
        "/api/dashboard/stats",
        "/api/oracle/health",
        "/bali-zero/chat-stream",
        "/api/knowledge/collections",
        "/api/oracle/personalities",
        "/api/oracle/gemini/test",
    ],
    # JWT endpoints (require user authentication)
    "jwt": [
        "/api/auth/*",
        "/api/team-activity/*",
        "/api/conversations/*",
        "/api/autonomous-agents/*",
    ],
    # Hybrid endpoints (accept both API Key and JWT)
    "hybrid": [
        "/api/search",
        "/api/crm/*",
        "/api/ingest/*",
        "/api/intel/*",
        "/api/memory-vector/*",
    ],
    # Admin only endpoints
    "admin_only": ["/api/auth/profile", "/api/admin/*"],
}


def classify_endpoint(path: str) -> str:
    """
    Classify endpoint path by security level

    Args:
        path: Endpoint path (e.g., "/api/dashboard/stats")

    Returns:
        Security level classification
    """
    for level, endpoints in ENDPOINT_CLASSIFICATION.items():
        if any(endpoint in path for endpoint in endpoints):
            return level

    # Default to hybrid for unclassified endpoints
    return SecurityLevel.HYBRID


def apply_security_by_endpoint(path: str):
    """
    Factory function to create decorators based on endpoint path classification

    Usage:
        @apply_security_by_endpoint("/api/dashboard/stats")
        async def dashboard_endpoint(request: Request):
            return {"stats": {...}}
    """
    security_level = classify_endpoint(path)

    if security_level == SecurityLevel.PUBLIC:
        return public_endpoint
    elif security_level == SecurityLevel.API_KEY:
        return api_key_required()
    elif security_level == SecurityLevel.JWT:
        return jwt_required
    elif security_level == SecurityLevel.ADMIN_ONLY:
        return role_required(["admin"])
    else:  # HYBRID
        return optional_auth
