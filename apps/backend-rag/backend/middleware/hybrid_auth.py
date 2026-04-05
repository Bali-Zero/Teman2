"""
Hybrid Authentication Middleware - Fail-Closed Implementation
Combines API Key, Cookie JWT, and Header JWT authentication for flexible access control.

Authentication Priority:
1. API Key (X-API-Key header) - for service-to-service communication
2. Header JWT (Authorization: Bearer) - frontend active session (takes precedence over cookie)
3. Cookie JWT (nz_access_token) - fallback for SSO/portal without Authorization header

SECURITY POLICY: Fail-Closed - any authentication system error denies access
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from backend.app.core.config import settings
from backend.app.services.api_key_auth import APIKeyAuth
from backend.app.utils.cookie_auth import get_jwt_from_cookie, is_csrf_exempt, validate_csrf

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
            },
        )

    # Development origins from settings
    if getattr(settings, "dev_origins", None):
        origins.update(
            {origin.strip() for origin in settings.dev_origins.split(",") if origin.strip()},
        )

    # Defaults (keep in sync with cors_config.py)
    defaults = {
        "https://balizero.com",  # Primary production domain
        "https://www.balizero.com",  # Primary production domain (www)
        "https://kita.balizero.com",
        "https://www.kita.balizero.com",
        "https://mail.balizero.com",  # Mail subdomain
        "https://calendar.balizero.com",  # Calendar subdomain
        "https://drive.balizero.com",  # Drive subdomain
        "https://knowledge.balizero.com",  # Knowledge subdomain
        "https://nuzantara-mouth.vercel.app",  # Frontend Vercel deployment
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

    def __init__(self, app) -> None:
        super().__init__(app)
        self.api_key_auth = APIKeyAuth()

        # Configure authentication settings
        self.api_auth_enabled = settings.api_auth_enabled
        self.api_auth_bypass_db = settings.api_auth_bypass_db

        # Define public endpoints that don't require authentication
        # SECURITY POLICY: Only endpoints that MUST be public for legitimate business reasons
        # Each endpoint has a documented business justification below
        self.public_endpoints = [
            # ========================================================================
            # INFRASTRUCTURE & MONITORING ENDPOINTS
            # ========================================================================
            "/",  # BUSINESS: Root path for simple connectivity checks
            "/health",  # BUSINESS: Health checks required by load balancers, monitoring systems
            "/health/",  # BUSINESS: Alternative health check path (common pattern)
            "/api/health",  # BUSINESS: Alternative health check path
            # SECURITY: /docs, /openapi.json, /redoc, /metrics moved to _is_protected_infra_endpoint()
            # They require admin API key in production, are unrestricted in dev/staging
            # ========================================================================
            # AUTHENTICATION ENDPOINTS (Must be public for initial login)
            # ========================================================================
            "/api/auth/team/login",  # BUSINESS: Team member login - must be public to allow initial authentication
            "/api/auth/login",  # BUSINESS: User login endpoint - must be public to allow initial authentication
            "/api/auth/csrf-token",  # BUSINESS: CSRF token generation - must be public for CSRF protection flow
            "/api/whatsapp/conversations",  # BUSINESS: Omnichannel dashboard - allowing access via proxy
            "/api/whatsapp/messages/",  # BUSINESS: Message history
            "/api/telegram/conversations",
            "/api/telegram/messages/",
            "/api/instagram/conversations",
            "/api/instagram/messages/",
            "/api/workflow/",
            # ========================================================================
            # WEBHOOK ENDPOINTS (Verified by secret tokens/signatures)
            # ========================================================================
            "/webhook/whatsapp",  # BUSINESS: Meta WhatsApp webhook - verified by WHATSAPP_VERIFY_TOKEN
            "/api/whatsapp/webhook",  # ALIAS: Meta WhatsApp webhook (legacy URL configured in Meta Dashboard)
            "/webhook/instagram",  # BUSINESS: Meta Instagram webhook - verified by INSTAGRAM_VERIFY_TOKEN
            "/webhook/twitter",  # BUSINESS: X/Twitter Account Activity webhook - verified by HMAC signature
            "/api/telegram/webhook",  # BUSINESS: Telegram bot webhook (legacy path)
            "/webhook/telegram",  # BUSINESS: Telegram bot webhook (multi-channel architecture)
            "/api/webhook/telegram",  # BUSINESS: Telegram bot webhook (api-prefixed path)
            # ========================================================================
            # OAUTH CALLBACK ENDPOINTS (Public by OAuth 2.0 specification)
            # ========================================================================
            "/api/integrations/zoho/callback",  # BUSINESS: Zoho OAuth callback - required by OAuth 2.0 flow
            "/api/integrations/google-drive/callback",  # BUSINESS: Google Drive OAuth callback - required by OAuth 2.0 flow
            "/api/integrations/google-drive/system/status",  # BUSINESS: OAuth status check - REVIEW: Should require auth
            "/api/admin/drive/health",  # BUSINESS: Drive health check - public status for diagnostics
            # SECURITY: /api/admin/drive/poll, /backfill, /refresh, /service-account-status, /test-list-files
            # moved to API key auth — these are write/admin operations that must not be public.
            # Air cron must send X-API-Key header for /poll.
            "/admin/google-drive/callback-system",  # BUSINESS: Admin OAuth callback (public per OAuth 2.0 spec)
            "/admin/zoho/callback",  # BUSINESS: Admin Zoho OAuth callback (public per OAuth 2.0 spec)
            # SECURITY: /admin/google-drive/auth-system and /admin/zoho/auth removed from public.
            # OAuth initiation requires admin auth to prevent unauthorized OAuth flows.
            # SECURITY: ALL /test/* endpoints REMOVED from public (2026-03-24 security audit).
            # These allowed unauthenticated invoice triggers, client email updates, and practice listing.
            # They now require API key or admin JWT auth.
            # ========================================================================
            # CLIENT PORTAL ENDPOINTS (Public for client self-service)
            # ========================================================================
            "/api/portal/invite/validate/",  # BUSINESS: Client invitation validation - token-based security
            "/api/portal/invite/complete",  # BUSINESS: Client registration completion - token-based security
            # ========================================================================
            # PUBLIC KNOWLEDGE BASE ENDPOINTS
            # ========================================================================
            "/api/knowledge/visa",  # BUSINESS: Public visa types knowledge base - informational content for website visitors
            "/api/agentic-rag/stream",  # BUSINESS: AI Chat streaming endpoint - public for Prime map widget (rate-limited: 10/min)
            "/api/agentic-rag/query",  # BUSINESS: Prime Intelligence AI chat - public anonymous for map intelligence (rate-limited: 10/min)
            "/api/oracle/health",  # BUSINESS: Oracle health check - public status endpoint
            "/api/agent/health",  # BUSINESS: LangGraph agent layer health check - public status endpoint for monitoring
            "/api/cell/metrics",  # BUSINESS: CELL ErrorRateSensor reads this internally — no user data exposed
            "/api/v1/kbli-notebook/",  # BUSINESS: KBLI Explorer - public business classification search, inspect, and chat
            "/api/v1/visa-oracle/",  # BUSINESS: Visa Oracle - public anonymous visa recommendation product
            "/api/webhook/chat",  # BUSINESS: Public AI chat webhook for website visitors
            "/api/webhook/chat/history",  # BUSINESS: Public chat history retrieval for session persistence
            # ========================================================================
            # BLOG & MARKETING ENDPOINTS (Public for website visitors)
            # ========================================================================
            "/api/news",  # BUSINESS: Public news/intel feed - approved articles for balizero.com homepage and blog
            "/api/blog/",  # BUSINESS: Public blog articles and content
            "/api/vitals",  # BUSINESS: Frontend performance telemetry
            "/api/blog/newsletter/subscribe",  # BUSINESS: Newsletter subscription - public marketing endpoint
            "/api/blog/newsletter/confirm",  # BUSINESS: Newsletter confirmation - token-based verification
            "/api/blog/newsletter/unsubscribe",  # BUSINESS: Newsletter unsubscribe - token-based verification (legal requirement)
            "/api/blog/ask",  # BUSINESS: AskZantara widget on blog articles - public Q&A feature
            # ========================================================================
            # PREVIEW ENDPOINTS (Public for content preview)
            # ========================================================================
            "/preview/",  # BUSINESS: Article preview pages for Telegram approval - no indexing, public preview
            "/api/dashboard/map/",  # BUSINESS: Streamlit dashboard — KBLI validation, client geo, risk zones, stats
            "/api/prime/zoning",  # BUSINESS: Prime Intelligence geospatial zoning API - public map intelligence layer
            "/api/prime/v2/resolve",  # BUSINESS: Prime Nexus Layer 1 - public spatial resolution (no auth)
            "/api/prime/v2/analyze",  # BUSINESS: Prime Nexus Layer 2 - public investment analysis (rate-limited: 10/min)
            "/api/prime/v2/health",   # BUSINESS: Prime Nexus health check - public status endpoint
            # ========================================================================
            # INTERNAL SERVICE ENDPOINTS - REMOVED FROM PUBLIC (Now require API key)
            # ========================================================================
            # SECURITY: These endpoints now require X-API-Key header authentication
            # Protected via verify_internal_api_key dependency in routers:
            # - /api/intel/scraper/submit - Requires API key (intel.py)
            # - /api/intel/staging/approve/ - Requires API key (intel.py)
            # - /api/legal/parent-documents - Requires API key (legal_ingest.py)
            # - /api/audio/ - Requires API key (audio.py)
            # - /preview/upload - Requires API key (preview.py)
        ]

        # SECURITY: Removed TEMPORARY/FIX/DEBUG endpoints:
        # - "/api/fix/users-auth" - REMOVED: No router implementation found
        # - "/api/fix/check-user/" - REMOVED: No router implementation found
        # - "/api/fix/test-login" - REMOVED: No router implementation found
        # - "/api/debug/migrate" - REMOVED: Debug endpoint should require ADMIN_API_KEY

        logger.info(
            f"HybridAuthMiddleware initialized - API Auth: {self.api_auth_enabled}, "
            f"Bypass DB: {self.api_auth_bypass_db}, Public Endpoints: {len(self.public_endpoints)}",
        )

    # Paths that require admin API key in production (docs, metrics)
    _PROTECTED_INFRA_PATHS = frozenset(
        {
            "/docs",
            "/docs/",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/redoc",
        },
    )
    _METRICS_PATHS = frozenset({"/metrics", "/metrics/"})

    def _is_protected_infra_endpoint(self, request: Request) -> bool:
        """
        Check if request is for docs/metrics endpoints.
        In production: requires admin API key (or Fly.io internal network for metrics).
        In dev/staging: always allowed.
        """
        path = request.url.path
        is_docs = path in self._PROTECTED_INFRA_PATHS or path.startswith("/docs")
        is_metrics = path in self._METRICS_PATHS

        if not is_docs and not is_metrics:
            return False

        # Non-production: always allow
        env = os.getenv("ENVIRONMENT", "production")
        if env != "production":
            return True

        # Metrics: allow from Fly.io internal network or localhost
        if is_metrics:
            client_ip = request.client.host if request.client else ""
            if client_ip.startswith("fdaa:") or client_ip in ("127.0.0.1", "::1"):
                return True

        # Production: require admin API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user_ctx = self.api_key_auth.validate_api_key(api_key)
            if user_ctx and user_ctx.get("role") in ("admin", "internal"):
                return True

        return False

    def is_public_endpoint(self, request: Request) -> bool:
        """Check if the requested endpoint is public (no auth required)"""
        path = request.url.path

        # Check protected infrastructure endpoints (docs, metrics)
        if self._is_protected_infra_endpoint(request):
            return True

        # Root path: exact match only (avoid "/" matching every path via startswith)
        if path in ("/", ""):
            return True

        is_public = any(path.startswith(ep) for ep in self.public_endpoints if ep not in ("/", ""))

        # Debug log for KBLI endpoints
        if "kbli" in path.lower():
            logger.info(f"🔍 KBLI endpoint check: path={path}, is_public={is_public}")
            matching_endpoints = [ep for ep in self.public_endpoints if path.startswith(ep)]
            logger.info(f"🔍 Matching public endpoints: {matching_endpoints}")

        return is_public

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
                path = request.url.path
                if path in ("/health", "/api/health"):
                    # Skip verbose logging for health check (called every 15s by Fly)
                    response = await call_next(request)
                    response.headers["X-Auth-Type"] = "public"
                    return response

                # Log structured access to public endpoints for security audit
                correlation_id = _get_correlation_id(request)
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent", "unknown")

                logger.info(
                    "Public endpoint accessed",
                    extra={
                        "event_type": "public_endpoint_access",
                        "endpoint": path,
                        "method": request.method,
                        "client_ip": client_ip,
                        "user_agent": user_agent[:200],
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Record metrics for public endpoint access
                try:
                    from backend.app.metrics import (
                        public_endpoint_access_by_ip,
                        public_endpoint_access_total,
                    )

                    # Record total access
                    public_endpoint_access_total.labels(
                        endpoint=request.url.path, method=request.method,
                    ).inc()

                    # Record access by IP (for abuse detection)
                    public_endpoint_access_by_ip.labels(
                        endpoint=request.url.path, client_ip=client_ip,
                    ).inc()
                except (ImportError, AttributeError):
                    # Metrics not available, continue without metrics
                    logger.debug("Metrics not available for public endpoint tracking")

                response = await call_next(request)
                response.headers["X-Auth-Type"] = "public"
                return response

            # Step 2: Apply authentication if enabled (all non-public endpoints)
            if self.api_auth_enabled:
                auth_result = await self.authenticate_request(request)

                # Fail-Closed: authentication required for non-public endpoints
                if not auth_result:
                    logger.debug(
                        f"Authentication failed for: {request.url.path} from {request.client.host}",
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
                request.state.auth_type = auth_result.get("auth_method", "unknown")

                user_email = auth_result.get("email", "unknown")
                logger.debug(
                    f"Request authenticated: {request.url.path} - "
                    f"User: {user_email} via {request.state.auth_type}",
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
                f"Detail: {exc.detail if isinstance(exc.detail, str) else 'See detail object'}",
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
                    f"Original detail type: {type(exc.detail)}",
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
            except Exception as e:
                logger.error(f"Error sanitizing authentication exception: {e}", exc_info=True)
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
        2. Header JWT (Authorization: Bearer) - frontend active session (takes precedence)
        3. Cookie JWT (nz_access_token) - fallback for SSO/portal without Authorization header

        Returns user context if authenticated, None if authentication fails
        SECURITY: None result = access denied (handled by dispatch)
        """
        client_host = request.client.host if request.client else "unknown"

        # Priority 0: Admin API Key via X-Debug-Key header (for admin/cron endpoints)
        debug_key = request.headers.get("X-Debug-Key")
        if debug_key and settings.admin_api_key and debug_key == settings.admin_api_key:
            logger.info(f"Admin key authenticated via X-Debug-Key from {client_host}")
            return {"role": "admin", "email": "admin@internal", "auth_method": "admin_key", "user_id": "admin"}

        # Priority 1: API Key Authentication (fastest, bypasses database)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Log authentication attempt without exposing API key
            logger.debug(f"API Key authentication attempt from {client_host}")
            user_context = self.api_key_auth.validate_api_key(api_key)
            if user_context:
                logger.info(
                    f"API Key authenticated: {user_context.get('role', 'unknown')} from {client_host}",
                )
                return user_context
            else:
                # API Key provided but invalid = immediate failure
                logger.warning(f"Invalid API Key attempt from {client_host}")
                return None

        # Priority 2: Header JWT Authentication (takes precedence over cookie when present)
        # When the frontend sends Authorization header, it represents the CURRENT session.
        # The cookie may be stale from a previous user's session (SSO on .balizero.com).
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            if not self.api_auth_bypass_db:
                logger.debug(f"Header JWT authentication attempt from {client_host}")
                jwt_user = await self.authenticate_jwt(request)
                if jwt_user:
                    jwt_user["auth_method"] = "jwt_header"
                    logger.info(
                        f"Header JWT authenticated: {jwt_user.get('email', 'unknown')} from {client_host}",
                    )
                    return jwt_user
                else:
                    # JWT provided but invalid = immediate failure
                    logger.debug(f"Invalid Header JWT from {client_host}")
                    return None
            else:
                logger.warning("JWT authentication bypassed by configuration")
                return None

        # Priority 3: Cookie JWT Authentication (fallback for browser clients without Authorization header)
        cookie_token = get_jwt_from_cookie(request)
        if cookie_token:
            logger.debug(f"Cookie JWT authentication attempt from {client_host}")

            # Validate CSRF for state-changing requests (POST, PUT, DELETE, PATCH)
            if settings.csrf_enabled and not is_csrf_exempt(request) and not validate_csrf(request):
                logger.warning(
                    f"CSRF validation failed for {request.method} {request.url.path} from {client_host}",
                )
                return None

            jwt_user = await self.authenticate_jwt_token(cookie_token)
            if jwt_user:
                jwt_user["auth_method"] = "jwt_cookie"
                logger.info(
                    f"Cookie JWT authenticated: {jwt_user.get('email', 'unknown')} from {client_host}",
                )
                return jwt_user
            else:
                # Cookie JWT provided but invalid = immediate failure
                logger.warning(f"Invalid Cookie JWT from {client_host}")
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
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
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
                jwt_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
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
            logger.debug(f"JWT validation failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected JWT error: {e}")
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
