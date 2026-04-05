"""
FastAPI Dependency Injection

Centralized dependencies for all routers to avoid circular imports.
Provides fail-fast behavior with clear error messages for service unavailability.

ARCHITECTURE:
- Services are initialized in app.setup.service_initializer::initialize_services()
- Services are stored in app.state (FastAPI standard)
- This module provides getter functions that routers can use via Depends()

PATTERN:
- All dependencies use Request object to access app.state
- This allows easy mocking in tests
- Fail-fast: raises HTTPException if service not initialized

See: app.setup.service_initializer::initialize_services() for initialization logic
Note: main_cloud.py still exports initialize_services() for backward compatibility
"""

import logging
from typing import Annotated, Any, cast

import asyncpg
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.core.cache import CacheService, get_cache_service
from backend.llm.zantara_ai_client import ZantaraAIClient
from backend.services.memory import MemoryServicePostgres
from backend.services.routing.intelligent_router import IntelligentRouter
from backend.services.search.search_service import SearchService

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer(auto_error=False)


def get_search_service(request: Request) -> SearchService:
    """
    Dependency injection for SearchService.

    Provides singleton SearchService instance to all endpoints.
    Eliminates Qdrant client duplication in Oracle routers.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        SearchService: Singleton instance with Qdrant vector database

    Raises:
        HTTPException: 503 if service not initialized with detailed error info
    """
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SearchService unavailable",
                "message": "The search service failed to initialize. Check server logs.",
                "retry_after": 30,
                "service": "search",
                "troubleshooting": [
                    "Verify Qdrant is running and accessible",
                    "Check QDRANT_URL environment variable",
                    "Review application startup logs for errors",
                ],
            },
        )
    return cast(SearchService, service)


def get_ai_client(request: Request) -> ZantaraAIClient:
    """
    Get AI client or fail with clear error.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        ZantaraAIClient: The initialized AI client

    Raises:
        HTTPException: 503 if AI service not initialized
    """
    ai_client = getattr(request.app.state, "ai_client", None)
    if ai_client is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service unavailable",
                "message": "The AI service failed to initialize. Check API keys and configuration.",
                "retry_after": 60,
                "service": "ai",
                "troubleshooting": [
                    "Verify OPENAI_API_KEY or GOOGLE_API_KEY is set",
                    "Check API key validity and quota",
                    "Review application startup logs for errors",
                ],
            },
        )
    return cast(ZantaraAIClient, ai_client)


def get_intelligent_router(request: Request) -> IntelligentRouter:
    """
    Dependency injection for Intelligent Router.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        IntelligentRouter: Router instance for handling WhatsApp and other integrations

    Raises:
        HTTPException: 503 if router not initialized
    """
    router = getattr(request.app.state, "intelligent_router", None)
    if router is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Router unavailable",
                "message": "The intelligent router failed to initialize.",
                "retry_after": 30,
                "service": "router",
                "troubleshooting": [
                    "Check that critical services (Search, AI) initialized successfully",
                    "Review application startup logs for errors",
                ],
            },
        )
    return cast(IntelligentRouter, router)


def get_memory_service(request: Request) -> MemoryServicePostgres:
    """
    Dependency injection for Memory Service.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        MemoryServicePostgres: The initialized memory service

    Raises:
        HTTPException: 503 if memory service not initialized
    """
    memory_service = getattr(request.app.state, "memory_service", None)
    if memory_service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Memory service unavailable",
                "message": "The memory service failed to initialize. Database may be unavailable.",
                "retry_after": 30,
                "service": "memory",
                "troubleshooting": [
                    "Verify DATABASE_URL is configured",
                    "Check PostgreSQL connection",
                    "Review application startup logs for errors",
                ],
            },
        )
    return cast(MemoryServicePostgres, memory_service)


def get_database_pool(request: Request) -> asyncpg.Pool | None:
    """
    Dependency injection for database connection pool.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        asyncpg.Pool | None: The database connection pool, or None if unavailable.
            Returns None instead of raising exception to allow graceful degradation.

    Note:
        Some endpoints may require database and should check for None explicitly.
        Others can work with degraded functionality when database is unavailable.
    """
    # Get db_pool from backend.app.state
    # Use direct attribute access with fallback to handle edge cases
    db_pool = getattr(request.app.state, "db_pool", None)

    # Additional check: verify pool is actually usable (not just present)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        # Fail fast in tests and surface a clear 503 for API callers that require DB
        # Use string detail instead of dict to avoid JSON serialization issues with Pool objects
        db_init_error = getattr(request.app.state, "db_init_error", None)
        error_message = "The database connection pool is not initialized."
        if db_init_error:
            error_message += f" Initialization error: {db_init_error}"

        raise HTTPException(
            status_code=503,
            detail=error_message,  # Use string instead of dict to avoid serialization issues
            headers={
                "X-Error-Type": "database_unavailable",
                "Retry-After": "30",
            },
        )
    return db_pool


# Aliases for backward compatibility
get_database = get_database_pool
get_db = get_database_pool


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """
    Validate JWT token and return current user.

    Used by all protected endpoints to extract authenticated user information.

    Priority:
    1. Use request.state.user if set by HybridAuthMiddleware (cookie JWT auth)
    2. Fallback to validating Authorization header token (backward compatibility)

    Args:
        request: FastAPI Request object (to access request.state.user)
        credentials: HTTP Bearer token credentials from request header (optional if middleware authenticated)

    Returns:
        dict: User information with keys: email, user_id, role, permissions

    Raises:
        HTTPException: 401 if authentication fails
    """
    # Priority 1: Use user from middleware if available (cookie JWT auth)
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        # Ensure consistent format
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

        # Prioritize email over sub (sub is often UUID, we need email for memory)
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

    This is a convenience dependency that returns only the email string
    from the full user dict returned by get_current_user.

    Args:
        user: User dict from get_current_user dependency

    Returns:
        str: User's email address
    """
    return str(user["email"])


def require_team_member(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    Dependency that ensures the current user is a team member (not a client).

    Args:
        user: User information from get_current_user

    Returns:
        dict: The user information

    Raises:
        HTTPException: 403 if user is a client
    """
    if user.get("role") == "client":
        logger.warning(f"Access denied to client user: {user.get('email')}")
        raise HTTPException(
            status_code=403,
            detail="Access denied. This endpoint is only accessible to team members.",
        )
    return user


def get_cache(request: Request) -> CacheService:
    """
    Dependency injection for CacheService.

    Provides CacheService instance to all endpoints via FastAPI dependency injection.
    Uses singleton pattern internally but allows for test isolation.

    Args:
        request: FastAPI Request object (for consistency with other dependencies)

    Returns:
        CacheService: The cache service instance (singleton)

    Usage:
        from fastapi import Depends
        from backend.app.dependencies import get_cache

        @router.get("/endpoint")
        async def my_endpoint(cache: CacheService = Depends(get_cache)):
            value = cache.get("key")
            cache.set("key", "value", ttl=300)
    """
    # Try to get from backend.app.state first (if initialized there)
    cache_service = getattr(request.app.state, "cache_service", None)
    if cache_service is not None:
        return cast(CacheService, cache_service)

    # Fallback to singleton (for backward compatibility)
    return get_cache_service()


# ============================================================================
# ORCHESTRATOR DEPENDENCIES
# ============================================================================

# Global orchestrator instance (lazy-loaded)
_agentic_rag_orchestrator = None


def get_orchestrator(request: Request) -> Any:
    """
    Dependency injection for AgenticRAGOrchestrator.

    Provides singleton orchestrator instance to all RAG endpoints.
    Replaces global variable pattern used in agentic_rag.py and telegram.py.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        AgenticRAGOrchestrator: Singleton orchestrator instance

    Note:
        Uses lazy initialization to avoid circular imports at module load time.
    """
    global _agentic_rag_orchestrator

    if _agentic_rag_orchestrator is None:
        from backend.services.rag.agentic import create_agentic_rag

        db_pool = getattr(request.app.state, "db_pool", None)
        search_service = getattr(request.app.state, "search_service", None)
        nlm_enrichment_service = getattr(request.app.state, "nlm_enrichment_service", None)
        graph_service = getattr(request.app.state, "graph_service", None)
        cultural_insights = getattr(request.app.state, "cultural_insights", None)
        _agentic_rag_orchestrator = create_agentic_rag(
            retriever=search_service,
            db_pool=db_pool,
            nlm_enrichment_service=nlm_enrichment_service,
            graph_service=graph_service,
            cultural_insights_service=cultural_insights,
        )

    return _agentic_rag_orchestrator


def get_optional_database_pool(request: Request) -> Any:
    """
    Get database pool with graceful degradation.

    Unlike get_database_pool(), this returns None instead of raising
    HTTPException when database is unavailable. Use for endpoints that
    can work with reduced functionality.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        asyncpg.Pool | None: The pool, or None if unavailable
    """
    try:
        return get_database_pool(request)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


# ============================================================================
# QDRANT CLIENT DEPENDENCIES
# ============================================================================


def get_retriever(request: Request) -> Any:
    """
    Dependency injection for Qdrant retriever client.

    Provides access to the shared Qdrant client instance.
    Replaces direct QdrantClient() instantiation in routers.

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        The retriever instance with Qdrant client

    Raises:
        HTTPException: 503 if Qdrant not available
    """
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Vector database unavailable",
                "message": "Qdrant retriever not initialized.",
                "retry_after": 30,
                "service": "qdrant",
                "troubleshooting": [
                    "Verify QDRANT_URL is configured",
                    "Check Qdrant server is running",
                    "Review application startup logs",
                ],
            },
        )
    return retriever


# ============================================================================
# PORTAL CLIENT DEPENDENCIES
# ============================================================================


async def get_current_portal_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get current authenticated client from JWT token for Portal endpoints.

    This dependency is used by all Portal API endpoints (taxes, visa, documents)
    to authenticate and authorize client access. It validates that:
    1. User has valid JWT token (set by middleware)
    2. User role is 'client' (not team member)
    3. User has a linked client profile in the database

    Args:
        request: FastAPI Request object to access request.state.user
        db_pool: Database connection pool for client lookup

    Returns:
        dict: Client information with keys:
            - id: Client database ID (int)
            - email: Client email address (str)
            - full_name: Client full name (str)

    Raises:
        HTTPException 401: If no valid JWT token present
        HTTPException 403: If user role is not 'client'
        HTTPException 404: If client profile not found in database

    Usage:
        from fastapi import Depends
        from backend.app.dependencies import get_current_portal_client

        @router.get("/my-data")
        async def get_my_data(
            current_client: dict = Depends(get_current_portal_client)
        ):
            client_id = current_client["id"]
            # ... fetch client-specific data
    """
    # Check for authenticated user from middleware
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = request.state.user

    # Verify role is 'client' (not team member or admin)
    if user.get("role") != "client":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only accessible to clients",
        )

    # Look up linked client profile
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


# ============================================================================
# CHANNEL ROUTER DEPENDENCIES
# ============================================================================


def get_channel_router(request: Request) -> Any:
    """
    Get ChannelRouter for multi-channel architecture.

    The ChannelRouter is initialized in service_initializer.py during application startup.
    It manages adapters for different communication channels (Telegram, Web, WhatsApp, etc.).

    Args:
        request: FastAPI Request object to access app.state

    Returns:
        ChannelRouter: The initialized channel router instance

    Raises:
        HTTPException: 503 if channel router not initialized

    Usage:
        from fastapi import Depends
        from backend.app.dependencies import get_channel_router

        @router.post("/webhook/telegram")
        async def telegram_webhook(
            channel_router: ChannelRouter = Depends(get_channel_router)
        ):
            await channel_router.route_message("telegram", update)
    """
    channel_router = getattr(request.app.state, "channel_router", None)
    if channel_router is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Channel router unavailable",
                "message": "The multi-channel router failed to initialize. Check server logs.",
                "retry_after": 30,
                "service": "channel_router",
                "troubleshooting": [
                    "Verify all channel adapters are properly configured",
                    "Check environment variables (TELEGRAM_BOT_TOKEN, etc.)",
                    "Review application startup logs for errors",
                ],
            },
        )
    return channel_router
