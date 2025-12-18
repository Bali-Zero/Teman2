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

import asyncpg
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.cache import CacheService, get_cache_service
from llm.zantara_ai_client import ZantaraAIClient
from services.intelligent_router import IntelligentRouter
from services.memory_service_postgres import MemoryServicePostgres
from services.search_service import SearchService

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
    return service


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
    return ai_client


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
    return router


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
    return memory_service


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
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None:
        # Fail fast in tests and surface a clear 503 for API callers that require DB
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database unavailable",
                "message": "The database connection pool is not initialized.",
                "retry_after": 30,
                "service": "database",
                "troubleshooting": [
                    "Ensure DATABASE_URL is configured and reachable",
                    "Check PostgreSQL service status and credentials",
                    "Verify initialize_services() was executed at startup",
                ],
            },
        )
    return db_pool


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
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
        from app.core.config import settings

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
        from app.dependencies import get_cache

        @router.get("/endpoint")
        async def my_endpoint(cache: CacheService = Depends(get_cache)):
            value = cache.get("key")
            cache.set("key", "value", ttl=300)
    """
    # Try to get from app.state first (if initialized there)
    cache_service = getattr(request.app.state, "cache_service", None)
    if cache_service is not None:
        return cache_service

    # Fallback to singleton (for backward compatibility)
    return get_cache_service()
