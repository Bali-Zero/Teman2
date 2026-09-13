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

from backend.app.auth.public_endpoints import (
    PUBLIC_ENDPOINTS,
    find_entry,
    path_matches_template,
)
from backend.app.core.config import settings
from backend.app.services.api_key_auth import APIKeyAuth
from backend.app.utils.cookie_auth import get_jwt_from_cookie, is_csrf_exempt, validate_csrf
from backend.app.utils.logging_utils import sanitize_log_path
from backend.services.pii.violation_store import hash_subject
from backend.services.security.token_revocation import (
    RevocationStoreUnavailable,
    is_session_revoked,
)

logger = logging.getLogger(__name__)

_PII_RESTRICTED_PUBLIC_ENDPOINTS = frozenset({"/api/visa-oracle/evaluate"})

#: OPERATIONS whose 401 RESPONSE — body AND headers — is fixed by a frozen
#: product contract, so this middleware's generic `{"detail": "Authentication
#: required"}` is a contract violation even though the REFUSAL itself is
#: correct.
#:
#: This changes what a refusal LOOKS like and NOTHING else: the status stays
#: 401, `WWW-Authenticate: Bearer` stays on the response, the handler still
#: never runs, and no path listed here becomes public — public-ness is decided
#: one step earlier in `dispatch`, exclusively by `PUBLIC_ENDPOINTS`.
#:
#: GARUDA VOA: the five staff operations (`listStaffPractices`,
#: `getStaffPractice`, `assignPractice`, `transitionPractice`,
#: `resolveLateOrder`) declare `401 -> {"code": "SESSION_REQUIRED", ...}` in
#: `products/garuda-voa/contracts/openapi.yaml`, under that file's
#: `x-public-privacy-response-headers` anchor. The kita client reads `code`
#: for its error boundary and saw `undefined` on this path because this
#: middleware refuses before `garuda_staff_router` runs.
#:
#: The HEADERS are part of the contract, not decoration: serving the
#: contract's body without its `Cache-Control: no-store, private` would make
#: a shared cache eligible to store a refusal for an authenticated surface.
#: `garuda_staff_router._privacy_headers` puts the identical three on every
#: response it builds; this is the same statement for the refusals that never
#: reach it (refuter Codex `gpt-5.6-sol`, round-1 finding #2).
#:
#: Matched against the frozen OPERATION TEMPLATES, never against a bare path
#: prefix (cicatrix #3, guard-over-match — refuter rounds 1 #3 and 2 #3). A
#: prefix claims things the contract does not declare: the bare
#: `/api/visa/voa/staff`, which `garuda_voa.py`'s owner-archive route
#: `/api/visa/voa/{hash}` pattern-matches; the trailing-slash-only
#: `/api/visa/voa/staff/`; the malformed `/api/visa/voa/staff//practices`;
#: and any arbitrary descendant. Template matching is segment-COUNT-based, so
#: all four fail by construction rather than by vigilance. The templates are
#: a verbatim copy of the contract's own paths — never read from the YAML at
#: runtime (a middleware must not depend on a product file), pinned equal to
#: it by `test_hybrid_auth_contract_401_envelope.py`, the same discipline
#: `garuda_staff_router._ERROR_CATALOG` already follows for `errors.yaml`.
_CONTRACT_401_PRIVACY_HEADERS: dict[str, str] = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

_GARUDA_VOA_STAFF_OPERATIONS: tuple[str, ...] = (
    "/api/visa/voa/staff/practices",
    "/api/visa/voa/staff/practices/{practice_id}",
    "/api/visa/voa/staff/practices/{practice_id}/assignment",
    "/api/visa/voa/staff/practices/{practice_id}/transitions",
    "/api/visa/voa/staff/orders/{order_id}/late-resolution",
)

_CONTRACT_401_ENVELOPES: tuple[tuple[tuple[str, ...], dict[str, Any], dict[str, str]], ...] = (
    (
        _GARUDA_VOA_STAFF_OPERATIONS,
        {
            "code": "SESSION_REQUIRED",
            "retryable": False,
            "message_key": "garuda_voa.error.session_required",
        },
        _CONTRACT_401_PRIVACY_HEADERS,
    ),
)


def contract_401_envelope(path: str) -> tuple[dict[str, Any], dict[str, str]] | None:
    """The frozen-contract 401 `(body, headers)` for `path`, or None for the
    generic body.

    `path` is `request.url.path`, which carries any ASGI mount prefix. That is
    deliberate and not a gap this function may close on its own:
    `is_public_endpoint` reads the SAME attribute, so the entire public
    registry already resolves against the externally-visible path. A
    mount-aware reading here and a mount-blind one there would be strictly
    worse than both being consistent. `main_api:app` is served at the root by
    uvicorn in production (no `--root-path` in `apps/backend-rag/fly.toml`);
    if that ever changes, BOTH readers move together.

    Returns fresh dicts each call so a caller can never mutate the registry.
    """
    for templates, envelope, headers in _CONTRACT_401_ENVELOPES:
        if any(path_matches_template(path, template) for template in templates):
            return dict(envelope), dict(headers)
    return None


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

        # Public endpoints live in `backend/app/auth/public_endpoints.py`.
        # That registry is the single source of truth: every public route has
        # a documented reason and a category, and a CI test enforces drift in
        # both directions (registry ↔ mounted routes).
        self.public_endpoints = PUBLIC_ENDPOINTS

        logger.info(
            f"HybridAuthMiddleware initialized - API Auth: {self.api_auth_enabled}, "
            f"Bypass DB: {self.api_auth_bypass_db}, "
            f"Public Endpoints: {len(self.public_endpoints)}",
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

        entry = find_entry(path)
        is_public = entry is not None

        # Debug log for KBLI endpoints
        if "kbli" in path.lower():
            logger.info(
                f"🔍 KBLI endpoint check: path={path}, is_public={is_public}, "
                f"matched={entry.prefix if entry else None}",
            )

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
        log_path = sanitize_log_path(request.url.path)

        # Removed sensitive debug logging - headers contain auth tokens
        logger.debug("Middleware dispatching: %s", log_path)

        # Step 0: Allow CORS preflight requests (OPTIONS) to pass through
        if request.method == "OPTIONS":
            logger.debug("CORS preflight request: %s", log_path)
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
            client_reference = hash_subject(client_ip) or "unknown"
            user_agent = request.headers.get("user-agent", "unknown")
            matched_entry = find_entry(path)

            privacy_restricted = path in _PII_RESTRICTED_PUBLIC_ENDPOINTS
            access_context: dict[str, Any] = {
                "event_type": "public_endpoint_access",
                "endpoint": log_path,
                "method": request.method,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "bypass_reason": matched_entry.reason if matched_entry else "infra",
                "bypass_category": (matched_entry.category.value if matched_entry else "infra"),
                "bypass_prefix": matched_entry.prefix if matched_entry else None,
                "privacy_restricted": privacy_restricted,
            }
            if not privacy_restricted:
                access_context.update(
                    {
                        "client_ip": client_reference,
                        "user_agent": user_agent[:200],
                        "correlation_id": correlation_id,
                    },
                )

            logger.info(
                "Public endpoint accessed",
                extra=access_context,
            )

            try:
                from backend.app.metrics import (
                    public_endpoint_access_by_ip,
                    public_endpoint_access_total,
                )

                public_endpoint_access_total.labels(
                    endpoint=log_path,
                    method=request.method,
                ).inc()
                if not privacy_restricted:
                    public_endpoint_access_by_ip.labels(
                        endpoint=log_path,
                        client_ip=client_reference,
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
                client_reference = hash_subject(client_host) or "unknown"
                error_type = type(auth_exc).__name__

                logger.critical(
                    f"[{correlation_id}] Auth system failure — ACCESS DENIED: "
                    f"Type={error_type}, "
                    f"Request={request.method} {log_path} from {client_reference}",
                    exc_info=True,
                )

                from fastapi.responses import JSONResponse

                cors_headers = self._cors_headers_for_request(request)
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": "Authentication service temporarily unavailable",
                        "correlation_id": correlation_id,
                    },
                    headers={**cors_headers, "X-Correlation-ID": correlation_id},
                )

            if not auth_result:
                client_host = request.client.host if request.client else "unknown"
                client_reference = hash_subject(client_host) or "unknown"
                logger.debug(
                    "Authentication failed for: %s from %s",
                    log_path,
                    client_reference,
                )
                from fastapi.responses import JSONResponse

                cors_headers = self._cors_headers_for_request(request)
                contract_401 = contract_401_envelope(request.url.path)
                content: dict[str, Any] = {"detail": "Authentication required"}
                contract_headers: dict[str, str] = {}
                if contract_401 is not None:
                    content, contract_headers = contract_401
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=content,
                    headers={
                        "WWW-Authenticate": "Bearer",
                        **cors_headers,
                        **contract_headers,
                    },
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
        client_reference = hash_subject(client_host) or "unknown"
        log_path = sanitize_log_path(request.url.path)

        # Priority 0: Admin API Key via X-Debug-Key header (for admin/cron endpoints)
        debug_key = request.headers.get("X-Debug-Key")
        if debug_key and settings.admin_api_key and debug_key == settings.admin_api_key:
            logger.info("Admin key authenticated via X-Debug-Key from %s", client_reference)
            return {
                "role": "admin",
                "email": "admin@internal",
                "auth_method": "admin_key",
                "user_id": "admin",
            }

        # Priority 0.5: Internal Service Key via X-Internal-Key header (for
        # Pro-side scripts like wa-mirror-auto-promote-leads that bypass the
        # normal POST /api/crm/clients/ router and need to trigger
        # ensure-drive-folder). The matching settings field is
        # `wa_mirror_internal_key`; rotate via Fly secret WA_MIRROR_INTERNAL_KEY.
        # Returns an "internal" pseudo-user; downstream routers MUST treat
        # this as service-to-service, NOT a real user identity.
        internal_key = request.headers.get("X-Internal-Key")
        configured_internal = getattr(settings, "wa_mirror_internal_key", None)
        if internal_key and configured_internal and internal_key == configured_internal:
            logger.info("Internal service key authenticated from %s", client_reference)
            return {
                "role": "internal",
                "email": "wa-mirror-internal@balizero.com",
                "auth_method": "internal_key",
                "user_id": "wa-mirror-internal",
            }

        # Priority 1: API Key Authentication (fastest, bypasses database)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Log authentication attempt without exposing API key
            logger.debug("API Key authentication attempt from %s", client_reference)
            user_context = self.api_key_auth.validate_api_key(api_key)
            if user_context:
                logger.info(
                    "API Key authenticated: role=%s from %s",
                    user_context.get("role", "unknown"),
                    client_reference,
                )
                return user_context
            else:
                # API Key provided but invalid = immediate failure
                logger.warning("Invalid API Key attempt from %s", client_reference)
                return None

        # Priority 2: Header JWT Authentication (takes precedence over cookie when present)
        # When the frontend sends Authorization header, it represents the CURRENT session.
        # The cookie may be stale from a previous user's session (SSO on .balizero.com).
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            if not self.api_auth_bypass_db:
                logger.debug("Header JWT authentication attempt from %s", client_reference)
                jwt_user = await self.authenticate_jwt(request)
                if jwt_user:
                    jwt_user["auth_method"] = "jwt_header"
                    logger.info(
                        "Header JWT authenticated: role=%s from %s",
                        jwt_user.get("role", "unknown"),
                        client_reference,
                    )
                    return jwt_user
                else:
                    # JWT provided but invalid = immediate failure
                    logger.debug("Invalid Header JWT from %s", client_reference)
                    return None
            else:
                logger.warning("JWT authentication bypassed by configuration")
                return None

        # Priority 3: Cookie JWT Authentication (fallback for browser clients without Authorization header)
        cookie_token = get_jwt_from_cookie(request)
        if cookie_token:
            logger.debug("Cookie JWT authentication attempt from %s", client_reference)

            # Validate CSRF for state-changing requests (POST, PUT, DELETE, PATCH)
            if settings.csrf_enabled and not is_csrf_exempt(request) and not validate_csrf(request):
                logger.warning(
                    "CSRF validation failed for %s %s from %s",
                    request.method,
                    log_path,
                    client_reference,
                )
                return None

            jwt_user = await self.authenticate_jwt_token(cookie_token)
            if jwt_user:
                jwt_user["auth_method"] = "jwt_cookie"
                logger.info(
                    "Cookie JWT authenticated: role=%s from %s",
                    jwt_user.get("role", "unknown"),
                    client_reference,
                )
                return jwt_user
            else:
                # Cookie JWT provided but invalid = immediate failure
                logger.warning("Invalid Cookie JWT from %s", client_reference)
                return None

        # No authentication provided = failure for non-public endpoints
        logger.debug("No authentication provided for protected endpoint: %s", log_path)
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

            # Stateless validation using secret key. Expiry is mandatory.
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": True, "require_exp": True},
            )

            # Validate required fields
            if not payload.get("sub") or not payload.get("email"):
                logger.warning("JWT missing required claims (sub, email)")
                return None

            if await is_session_revoked(payload):
                logger.warning("Rejected revoked cookie JWT session")
                return None

            # Construct user context from token
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                # An absent role claim is NOT a colleague: "member" is a real staff
                # role, so defaulting to it let a role-less token through every
                # team gate (PENDING-ARMS row 88). Empty fails every allow-list.
                "role": payload.get("role") or "",
                "name": payload.get("name", payload.get("email").split("@")[0]),
                "status": "active",
            }

        except JWTError as e:
            logger.warning("JWT token validation failed: %s", e)
            return None
        except RevocationStoreUnavailable:
            raise
        except Exception as e:
            logger.warning("Unexpected JWT token error: %s", e)
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

            # Stateless validation using secret key. Expiry is mandatory.
            payload = jwt.decode(
                jwt_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": True, "require_exp": True},
            )

            # Validate required fields
            if not payload.get("sub") or not payload.get("email"):
                logger.warning("JWT missing required claims")
                return None

            if await is_session_revoked(payload):
                logger.warning("Rejected revoked header JWT session")
                return None

            # Construct user context from token
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                # An absent role claim is NOT a colleague: "member" is a real staff
                # role, so defaulting to it let a role-less token through every
                # team gate (PENDING-ARMS row 88). Empty fails every allow-list.
                "role": payload.get("role") or "",
                "auth_method": "jwt_stateless",
                "name": payload.get("name", payload.get("email").split("@")[0]),
                "status": "active",
            }

        except JWTError as e:
            logger.debug("JWT validation failed: %s", e)
            return None
        except RevocationStoreUnavailable:
            raise
        except Exception as e:
            logger.debug("Unexpected JWT error: %s", e)
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
