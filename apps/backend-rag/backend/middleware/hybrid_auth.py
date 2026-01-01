"""
Hybrid Authentication Middleware - Fail-Closed Implementation
Combines API Key, Cookie JWT, and Header JWT authentication for flexible access control.

Authentication Priority:
1. API Key (X-API-Key header) - for service-to-service communication
2. Cookie JWT (nz_access_token) - for browser clients with httpOnly cookies
3. Header JWT (Authorization: Bearer) - backward compatibility

SECURITY POLICY: Fail-Closed - any authentication system error denies access
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from app.core.config import settings
from app.services.api_key_auth import APIKeyAuth
from app.utils.cookie_auth import get_jwt_from_cookie, is_csrf_exempt, validate_csrf

logger = logging.getLogger(__name__)


def _get_correlation_id(request: Request) -> str:
    """Extract correlation ID from request state for logging"""
    return (
        getattr(request.state, "correlation_id", None)
        or getattr(request.state, "request_id", None)
        or "unknown"
    )


def _allowed_origins() -> set[str]:
    """
    Local helper to mirror CORS allowlist so we can attach headers even when
    authentication short-circuits the request.
    """
    origins: set[str] = set()

    # Production origins from settings
    if settings.zantara_allowed_origins:
        origins.update(
            {
                origin.strip()
                for origin in settings.zantara_allowed_origins.split(",")
                if origin.strip()
            }
        )

    # Development origins from settings
    if getattr(settings, "dev_origins", None):
        origins.update(
            {origin.strip() for origin in settings.dev_origins.split(",") if origin.strip()}
        )

    # Defaults (keep in sync with main_cloud.py)
    defaults = {
        "https://zantara.balizero.com",
        "https://www.zantara.balizero.com",
        "https://nuzantara-mouth.fly.dev",
        "http://localhost:3000",
    }
    origins.update(defaults)
    return origins


class HybridAuthMiddleware(BaseHTTPMiddleware):
    """
    Fail-Closed Hybrid Authentication Middleware that provides secure, flexible authentication:
    1. Public endpoints (health, docs, metrics) - no authentication required
    2. API Key authentication (fast, bypasses database dependency) - for internal services
    3. JWT authentication (production-grade) - for external users

    SECURITY POLICY: Fail-Closed - any authentication system error denies access
    """

    def __init__(self, app):
        super().__init__(app)
        self.api_key_auth = APIKeyAuth()

        # Configure authentication settings
        self.api_auth_enabled = settings.api_auth_enabled
        self.api_auth_bypass_db = settings.api_auth_bypass_db

        # Define public endpoints that don't require authentication
        self.public_endpoints = [
            "/health",
            "/health/",
            "/docs",
            "/docs/",
            "/openapi.json",
            "/api/v1/openapi.json",  # OpenAPI spec for contract verification
            "/redoc",
            "/metrics",
            "/metrics/",
            "/api/auth/team/login",  # Login endpoint must be public
            "/api/auth/login",  # Login endpoint must be public
            "/api/auth/csrf-token",  # CSRF token endpoint must be public
            # SECURITY: Removed /debug/config from public endpoints - requires authentication
            "/webhook/whatsapp",  # Meta webhook verification
            "/webhook/instagram",  # Meta webhook verification
            "/api/oracle/health",  # Oracle health check (public)
            "/api/debug/migrate",  # Temporary debug endpoint
            "/api/legal/parent-documents",  # Internal ingestion endpoint (no auth)
            "/api/portal/invite/validate/",  # Client invitation validation (public)
            "/api/portal/invite/complete",  # Client registration completion (public)
            "/api/integrations/zoho/callback",  # Zoho OAuth callback (public)
            "/api/integrations/google-drive/callback",  # Google Drive OAuth callback (public)
            "/api/audio/",  # Audio TTS/STT endpoints (public for now)
            "/api/knowledge/visa",  # Visa types knowledge base (public)
            "/api/blog/newsletter/subscribe",  # Newsletter subscription (public)
            "/api/blog/newsletter/confirm",  # Newsletter confirmation (public)
            "/api/blog/newsletter/unsubscribe",  # Newsletter unsubscribe (public)
        ]

        logger.info(
            f"HybridAuthMiddleware initialized - API Auth: {self.api_auth_enabled}, "
            f"Bypass DB: {self.api_auth_bypass_db}, Public Endpoints: {len(self.public_endpoints)}"
        )

    def is_public_endpoint(self, request: Request) -> bool:
        """Check if the requested endpoint is public (no auth required)"""
        path = request.url.path
        return any(path.startswith(endpoint) for endpoint in self.public_endpoints)

    async def dispatch(self, request: Request, call_next):
        """
        Fail-Closed request dispatch through authentication middleware

        Authentication Priority:
        1. CORS preflight (OPTIONS) - pass through for CORS middleware
        2. Public endpoints (health, docs, metrics) - no authentication
        3. API Key (X-API-Key header) - fastest, bypasses database
        4. JWT Token (Authorization header) - standard JWT flow

        SECURITY: Any authentication error = deny access (fail-closed)
        """
        # Removed sensitive debug logging - headers contain auth tokens
        logger.debug(f"Middleware dispatching: {request.url.path}")

        try:
            # Step 0: Allow CORS preflight requests (OPTIONS) to pass through
            # This is essential for browser-based clients to work with CORS
            if request.method == "OPTIONS":
                logger.debug(f"CORS preflight request: {request.url.path}")
                return await call_next(request)

            # Step 1: Check if this is a public endpoint
            if self.is_public_endpoint(request):
                logger.debug(f"Public endpoint accessed: {request.url.path}")
                response = await call_next(request)
                response.headers["X-Auth-Type"] = "public"
                return response

            # Step 2: Apply authentication if enabled (all non-public endpoints)
            if self.api_auth_enabled:
                auth_result = await self.authenticate_request(request)

                # Fail-Closed: authentication required for non-public endpoints
                if not auth_result:
                    logger.warning(
                        f"Authentication failed for: {request.url.path} from {request.client.host}"
                    )
                    from fastapi.responses import JSONResponse

                    cors_headers = self._cors_headers_for_request(request)
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Authentication required"},
                        headers={"WWW-Authenticate": "Bearer", **cors_headers},
                    )

                # Inject authenticated user context into request state
                request.state.user = auth_result
                request.state.auth_type = getattr(auth_result, "auth_method", "unknown")

                user_email = auth_result.get("email", "unknown")
                logger.debug(
                    f"Request authenticated: {request.url.path} - "
                    f"User: {user_email} via {request.state.auth_type}"
                )

            # Step 3: Process the authenticated request
            response = await call_next(request)

            # Step 4: Add auth metadata to response headers for monitoring
            if hasattr(request.state, "auth_type"):
                response.headers["X-Auth-Type"] = request.state.auth_type

            return response

        except HTTPException as exc:
            # HTTPException from dependency injection (e.g., get_database_pool) or endpoint handlers
            # Extract correlation ID for better tracing
            correlation_id = _get_correlation_id(request)
            client_host = request.client.host if request.client else "unknown"

            logger.warning(
                f"[{correlation_id}] HTTPException during request processing: "
                f"{exc.status_code} - {request.method} {request.url.path} from {client_host}. "
                f"Detail: {exc.detail if isinstance(exc.detail, str) else 'See detail object'}"
            )

            from fastapi.responses import JSONResponse

            # Sanitize exc.detail to avoid JSON serialization errors (e.g., Pool objects)
            sanitized_detail = exc.detail
            if isinstance(exc.detail, dict):
                # Create a copy and sanitize any non-serializable values
                sanitized_detail = {}
                for key, value in exc.detail.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        sanitized_detail[key] = value
                    elif isinstance(value, (list, tuple)):
                        # Recursively sanitize list items
                        sanitized_detail[key] = [
                            str(item)
                            if not isinstance(item, (str, int, float, bool, type(None)))
                            else item
                            for item in value
                        ]
                    else:
                        # Convert non-serializable objects to string
                        sanitized_detail[key] = str(value)
            elif not isinstance(exc.detail, (str, int, float, bool, type(None))):
                # If detail is not a basic type, convert to string
                sanitized_detail = str(exc.detail)

            cors_headers = self._cors_headers_for_request(request)
            try:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": sanitized_detail},
                    headers={**(exc.headers or {}), **cors_headers},
                )
            except (TypeError, ValueError) as serialization_error:
                # If sanitization failed, fallback to string representation
                logger.error(
                    f"[{correlation_id}] Failed to serialize HTTPException detail: {serialization_error}. "
                    f"Original detail type: {type(exc.detail)}"
                )
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "detail": "Service unavailable (error serializing response)",
                        "correlation_id": correlation_id,
                        "error_type": type(serialization_error).__name__,
                    },
                    headers={**(exc.headers or {}), **cors_headers},
                )
        except Exception as e:
            # FAIL-CLOSED: Any system error = deny access for security
            correlation_id = _get_correlation_id(request)
            client_host = request.client.host if request.client else "unknown"

            # Log detailed exception info BEFORE sanitization for debugging
            error_type = type(e).__name__
            error_module = getattr(type(e), "__module__", "unknown")
            error_repr = repr(e) if len(repr(e)) < 500 else repr(e)[:500] + "..."

            logger.critical(
                f"[{correlation_id}] Authentication system failure - ACCESS DENIED: "
                f"Type={error_type}, Module={error_module}, "
                f"Request={request.method} {request.url.path} from {client_host}, "
                f"Error={error_repr}",
                exc_info=True,
            )

            from fastapi.responses import JSONResponse

            # Safe error message extraction (avoid serializing non-serializable objects)
            # Extract only exception type and a generic message to avoid Pool serialization
            try:
                # Check if error might involve database/Pool without trying to serialize it
                if (
                    "Pool" in error_type
                    or "asyncpg" in error_type.lower()
                    or "database" in error_type.lower()
                    or "Database" in error_type
                ):
                    error_msg = "Database connection error during authentication"
                else:
                    # Try to get message safely, but fallback to type if it fails
                    try:
                        error_msg = str(e)
                        # Sanitize message to remove any Pool references
                        if "Pool" in error_msg or "asyncpg" in error_msg.lower():
                            error_msg = "Database connection error during authentication"
                        elif len(error_msg) > 200:
                            error_msg = f"{error_type}: {error_msg[:200]}..."
                    except (TypeError, ValueError, AttributeError):
                        error_msg = f"{error_type} error during authentication"
            except Exception:
                error_msg = "Authentication service error"

            cors_headers = self._cors_headers_for_request(request)
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": f"Authentication service temporarily unavailable: {error_msg}",
                    "correlation_id": correlation_id,
                    "error_type": error_type,
                },
                headers={**cors_headers, "X-Correlation-ID": correlation_id},
            )

    def _cors_headers_for_request(self, request: Request) -> dict[str, str]:
        origin = request.headers.get("origin")
        if origin and origin in _allowed_origins():
            # Mirror standard CORS middleware behavior for short-circuit responses
            return {
                "access-control-allow-origin": origin,
                "access-control-allow-credentials": "true",
            }
        return {}

    async def authenticate_request(self, request: Request) -> dict[str, Any] | None:
        """
        Fail-Closed hybrid authentication

        Authentication Priority:
        1. API Key (X-API-Key header) - for service-to-service communication
        2. Cookie JWT (nz_access_token) - for browser clients with httpOnly cookies
        3. Header JWT (Authorization: Bearer) - backward compatibility

        Returns user context if authenticated, None if authentication fails
        SECURITY: None result = access denied (handled by dispatch)
        """
        client_host = request.client.host if request.client else "unknown"

        # Priority 1: API Key Authentication (fastest, bypasses database)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Log authentication attempt without exposing API key
            logger.debug(f"API Key authentication attempt from {client_host}")
            user_context = self.api_key_auth.validate_api_key(api_key)
            if user_context:
                logger.info(
                    f"API Key authenticated: {user_context.get('role', 'unknown')} from {client_host}"
                )
                return user_context
            else:
                # API Key provided but invalid = immediate failure
                logger.warning(f"Invalid API Key attempt from {client_host}")
                return None

        # Priority 2: Cookie JWT Authentication (browser clients with httpOnly cookies)
        cookie_token = get_jwt_from_cookie(request)
        if cookie_token:
            logger.debug(f"Cookie JWT authentication attempt from {client_host}")

            # Validate CSRF for state-changing requests (POST, PUT, DELETE, PATCH)
            if settings.csrf_enabled and not is_csrf_exempt(request):
                if not validate_csrf(request):
                    logger.warning(
                        f"CSRF validation failed for {request.method} {request.url.path} from {client_host}"
                    )
                    return None

            jwt_user = await self.authenticate_jwt_token(cookie_token)
            if jwt_user:
                jwt_user["auth_method"] = "jwt_cookie"
                logger.info(
                    f"Cookie JWT authenticated: {jwt_user.get('email', 'unknown')} from {client_host}"
                )
                return jwt_user
            else:
                # Cookie JWT provided but invalid = immediate failure
                logger.warning(f"Invalid Cookie JWT from {client_host}")
                return None

        # Priority 3: Header JWT Authentication (backward compatibility)
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            if not self.api_auth_bypass_db:
                logger.debug(f"Header JWT authentication attempt from {client_host}")
                jwt_user = await self.authenticate_jwt(request)
                if jwt_user:
                    jwt_user["auth_method"] = "jwt_header"
                    logger.info(
                        f"Header JWT authenticated: {jwt_user.get('email', 'unknown')} from {client_host}"
                    )
                    return jwt_user
                else:
                    # JWT provided but invalid = immediate failure
                    logger.warning(f"Invalid Header JWT from {client_host}")
                    return None
            else:
                logger.warning("JWT authentication bypassed by configuration")
                return None

        # No authentication provided = failure for non-public endpoints
        logger.debug(f"No authentication provided for protected endpoint: {request.url.path}")
        return None

    async def authenticate_jwt_token(self, token: str) -> dict[str, Any] | None:
        """
        Validate a JWT token string directly (for cookie-based auth).

        Args:
            token: JWT token string

        Returns:
            User context dict if valid, None otherwise
        """
        try:
            from jose import JWTError, jwt

            # Stateless validation using secret key
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )

            # Validate required fields
            if not payload.get("sub") or not payload.get("email"):
                logger.warning("JWT missing required claims (sub, email)")
                return None

            # Construct user context from token
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "member"),
                "name": payload.get("name", payload.get("email").split("@")[0]),
                "status": "active",
            }

        except JWTError as e:
            logger.warning(f"JWT token validation failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected JWT token error: {e}")
            return None

    async def authenticate_jwt(self, request: Request) -> dict[str, Any] | None:
        """
        Stateless JWT authentication
        """
        try:
            from jose import JWTError, jwt

            # Extract JWT token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            jwt_token = auth_header[7:]  # Remove "Bearer " prefix

            # Stateless validation using secret key
            payload = jwt.decode(
                jwt_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )

            # Validate required fields
            if not payload.get("sub") or not payload.get("email"):
                logger.warning("JWT missing required claims")
                return None

            # Construct user context from token
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "member"),
                "auth_method": "jwt_stateless",
                "name": payload.get("name", payload.get("email").split("@")[0]),
                "status": "active",
            }

        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected JWT error: {e}")
            return None

    def get_auth_stats(self) -> dict[str, Any]:
        """Get authentication statistics for monitoring"""
        return {
            "api_auth_enabled": self.api_auth_enabled,
            "api_auth_bypass_db": self.api_auth_bypass_db,
            "api_key_stats": self.api_key_auth.get_service_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def create_default_user_context() -> dict[str, Any]:
    """Create default user context for public endpoints"""
    return {
        "id": "public_user",
        "email": "public@zantara.dev",
        "name": "Public User",
        "role": "public",
        "status": "active",
        "auth_method": "public",
        "permissions": ["read"],
        "metadata": {
            "source": "hybrid_auth_middleware",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }
