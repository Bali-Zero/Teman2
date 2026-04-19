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

from fastapi import status
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
            # REMOVED: conversation endpoints require auth (security audit 2026-04-03)
            # "/api/whatsapp/conversations",  # Now requires JWT/API key
            # "/api/whatsapp/messages/",
            # "/api/telegram/conversations",
            # "/api/telegram/messages/",
            # "/api/instagram/conversations",
            # "/api/instagram/messages/",
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
            "/api/hr/late-reply/",  # BUSINESS: HR late check-in reply form - per-incident token-based security (secrets.compare_digest), GET form + POST submit, no PII collected. Token IS the auth.
            # ========================================================================
            # PUBLIC KNOWLEDGE BASE ENDPOINTS
            # ========================================================================
            "/api/knowledge/visa",  # BUSINESS: Public visa types knowledge base - informational content for website visitors
            # "/api/agentic-rag/stream"  # REMOVED: F-7 security fix — requires auth,  # BUSINESS: AI Chat streaming - allowing access to fix 401 issues
            # "/api/agentic-rag/query"  # REMOVED: F-7 security fix — requires auth,  # BUSINESS: Prime Intelligence AI chat - public anonymous access for map intelligence
            "/api/oracle/health",  # BUSINESS: Oracle health check - public status endpoint
            "/api/agent/health",  # BUSINESS: LangGraph agent layer health check - public status endpoint for monitoring
            "/api/cell/metrics",  # BUSINESS: CELL ErrorRateSensor reads this internally — no user data exposed
            "/api/v1/kbli-notebook/",  # BUSINESS: KBLI Explorer - public business classification search, inspect, and chat
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
            # ========================================================================
            # FUNNEL HUB — PRE-AUTH LEAD TRACKING (v2 L1 Funnel Hub)
            # ========================================================================
            "/api/funnel/session/touch",  # BUSINESS: Pre-auth lead cookie bz_session touch — anonymous UUID, no PII. Required for cross-funnel session attribution (visa/kbli/tax/property/home).
            "/api/funnel/session/convert",  # BUSINESS: Lead→client conversion bridge (called by portal login flow). Takes session_id + client_id.
            "/api/analytics/funnel-event",  # BUSINESS: 11 whitelisted funnel events (see packages/core/analytics/funnel-view.ts FUNNEL_EVENTS). No PII — session_id only.
            # ========================================================================
            # HOMEPAGE 4-APP (Visa Check + KBLI + Tax + Zoning) — public, no-PII
            # ========================================================================
            # Each app persists context in visa_checks/kbli_checks/etc. with a random
            # hash as the public id. Lead capture stores the intent + wa.me URL with
            # a 7-day TTL (see migration 119). No account, no PII stored beyond what
            # the user types into the handoff form.
            "/api/lead/capture",  # BUSINESS: 4-app homepage → WhatsApp handoff. POST only; returns wa.me URL.
            "/api/visa/check/start",  # BUSINESS: Branch selector (Clock vs Match) for Visa Check app.
            "/api/visa/clock",  # BUSINESS: Visa Clock submission + shareable /visa/clock/{hash} lookup.
            "/api/visa/match",  # BUSINESS: Visa Match submission + shareable /visa/match/{hash} lookup.
            "/api/funnel_email/unsubscribe/",  # BUSINESS: One-click email unsubscribe (token-based, CAN-SPAM compliant).
            "/api/prime/zoning",  # BUSINESS: Prime Intelligence geospatial zoning API - public map intelligence layer
            "/api/prime/zones-geojson",  # BUSINESS: Zone polygon GeoJSON for 3D map rendering (public)
            "/api/prime/v2/resolve",  # PRIME NEXUS: Layer 1 spatial resolution (public zone data)
            "/api/prime/v2/analyze",  # PRIME NEXUS: Layer 2 investment analysis (public, rate-limited)
            "/api/prime/v2/density",  # PRIME NEXUS: Competitor density per zone (public)
            "/api/prime/v2/predict",  # PRIME NEXUS: Zone trend prediction (public)
            "/api/prime/v2/temporal",  # PRIME NEXUS: Temporal activity (public — zone-level only)
            "/api/prime/v2/regulations",  # PRIME NEXUS: Regulation feed per zone (public)
            "/api/prime/v2/proposal/",  # PRIME NEXUS: Public proposal view (token-based)
            "/api/prime/v2/health",  # PRIME NEXUS: Health check
            # ========================================================================
            # VISA ORACLE ENDPOINTS (Public product — anonymous visa recommendations)
            # ========================================================================
            "/api/v1/visa-oracle/recommend",  # BUSINESS: Anonymous visa quiz recommendations — no user data, pure scoring logic
            "/api/v1/visa-oracle/chat",  # BUSINESS: Anonymous visa Q&A chat — rate-limited by IP hash, no PII collected
            "/api/v1/visa-oracle/handoff",  # BUSINESS: WhatsApp/Telegram handoff — builds deep-link URL + team notification
            "/api/v1/visa-oracle/visa-types",  # BUSINESS: Visa types catalog — used by Next.js SSG at build time
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
            # ========================================================================
            # PHASE 1 ORGANISM BRIDGE (Pro<->Fly bidirectional nerve)
            # ========================================================================
            # SECURITY: /api/bridge/* uses dedicated X-Bridge-Auth header with
            # hmac.compare_digest constant-time comparison against BRIDGE_API_KEY env
            # var (see backend/app/routers/bridge.py:_check_auth). The router itself
            # rejects unauthorized requests with 401 (Invalid bridge credentials) or
            # 503 (Bridge auth not configured). Bypassing JWT/API-key middleware here
            # is the explicit design — the bridge is M2M traffic from Pro local
            # network, not user-facing.
            "/api/bridge/",  # BUSINESS: Pro<->Fly bidirectional bridge (Phase 1 Sinapsi)
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

        # Step 0: Allow CORS preflight requests (OPTIONS) to pass through
        if request.method == "OPTIONS":
            logger.debug(f"CORS preflight request: {request.url.path}")
            return await call_next(request)

        # Step 1: Check if this is a public endpoint
        if self.is_public_endpoint(request):
            path = request.url.path
            if path in ("/health", "/api/health"):
                response = await call_next(request)
                response.headers["X-Auth-Type"] = "public"
                return response

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

            try:
                from backend.app.metrics import (
                    public_endpoint_access_by_ip,
                    public_endpoint_access_total,
                )
                public_endpoint_access_total.labels(
                    endpoint=request.url.path, method=request.method,
                ).inc()
                public_endpoint_access_by_ip.labels(
                    endpoint=request.url.path, client_ip=client_ip,
                ).inc()
            except (ImportError, AttributeError) as exc:
                # Metrics subsystem not wired in this deployment (e.g. tests,
                # minimal CI). Log once per process at debug — a missing
                # counter must NOT break a public endpoint.
                logger.debug(
                    "hybrid_auth.public_metrics_unavailable",
                    extra={"error_type": type(exc).__name__},
                )

            response = await call_next(request)
            response.headers["X-Auth-Type"] = "public"
            return response

        # Step 2: Authenticate (isolated try/except — auth errors → 503)
        if self.api_auth_enabled:
            try:
                auth_result = await self.authenticate_request(request)
            except Exception as auth_exc:
                # Auth system failure → fail-closed 503
                correlation_id = _get_correlation_id(request)
                client_host = request.client.host if request.client else "unknown"
                error_type = type(auth_exc).__name__

                logger.critical(
                    f"[{correlation_id}] Auth system failure — ACCESS DENIED: "
                    f"Type={error_type}, "
                    f"Request={request.method} {request.url.path} from {client_host}",
                    exc_info=True,
                )

                from fastapi.responses import JSONResponse
                cors_headers = self._cors_headers_for_request(request)
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": "Authentication service temporarily unavailable",
                        "correlation_id": correlation_id,
                        "error_type": error_type,
                    },
                    headers={**cors_headers, "X-Correlation-ID": correlation_id},
                )

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

            request.state.user = auth_result
            request.state.auth_type = auth_result.get("auth_method", "unknown")

        # Step 3: Process the request. HTTPException is caught here and
        # converted to a JSONResponse so middleware unit tests that bypass
        # FastAPI's global exception handlers can still observe the HTTP
        # status code. In a real request flow, FastAPI's global handler
        # would do the same conversion if we let the exception propagate,
        # so this catch is behaviourally equivalent in production.
        from fastapi import HTTPException as _HTTPException
        from fastapi.responses import JSONResponse as _JSONResponse

        try:
            response = await call_next(request)
        except _HTTPException as http_exc:
            detail = http_exc.detail
            try:
                content = {"detail": detail}
                cors_headers = self._cors_headers_for_request(request)
                headers = {**cors_headers, **(http_exc.headers or {})}
                return _JSONResponse(
                    status_code=http_exc.status_code,
                    content=content,
                    headers=headers,
                )
            except (TypeError, ValueError):
                # Detail may contain non-serializable objects — coerce to str
                cors_headers = self._cors_headers_for_request(request)
                headers = {**cors_headers, **(http_exc.headers or {})}
                return _JSONResponse(
                    status_code=http_exc.status_code,
                    content={"detail": str(detail)},
                    headers=headers,
                )

        if hasattr(request.state, "auth_type"):
            response.headers["X-Auth-Type"] = request.state.auth_type

        return response

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
            # S03: Two-phase JWT expiry enforcement
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
                options={"verify_exp": getattr(settings, "jwt_enforce_expiry", False)},
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
            # S03: Two-phase JWT expiry enforcement
            payload = jwt.decode(
                jwt_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
                options={"verify_exp": getattr(settings, "jwt_enforce_expiry", False)},
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
