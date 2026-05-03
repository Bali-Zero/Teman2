"""
Service locator dependencies.

Provides access to initialized services stored in app.state.
All heavy imports (SearchService, ZantaraAIClient, etc.) are LAZY (inside functions)
to prevent import-time failures from cascading to all routers.
"""

import logging
from typing import Any, cast

from fastapi import HTTPException, Request

from backend.core.cache import get_cache_service  # noqa: E402 (needed at module level for mock patching)

logger = logging.getLogger(__name__)

__all__ = [
    "get_search_service",
    "get_ai_client",
    "get_intelligent_router",
    "get_memory_service",
    "get_cache",
    "get_channel_router",
]


def _degraded_services_list(request: Request) -> list[str]:
    """Return ``app.state.degraded_services`` as a sorted list of strings.

    P0-1 contract: dependencies surface the degraded set so clients can
    distinguish "search down" from "AI down" from "everything down" and
    apply the right retry / fallback. See cicatrix STRUCTURAL 2026-04-29
    "SearchService fail-fast → degraded mode" / brainstorm
    P0-1_searchservice_degraded_mode.md.
    """
    degraded = getattr(request.app.state, "degraded_services", None)
    if not degraded:
        return []
    # Sorted so the response is deterministic for consumers that compare
    # the field across requests (debug UIs, snapshot tests, etc.).
    return sorted(str(s) for s in degraded)


def get_search_service(request: Request) -> Any:
    """
    Dependency injection for SearchService.

    Raises:
        HTTPException 503: If service not initialized. Detail follows
        the P0-1 structured contract:
        ``{error, message, retry_after_seconds, retry_after,
            degraded_services, service, troubleshooting}``.
        ``retry_after`` is preserved for backward compatibility;
        ``retry_after_seconds`` is the canonical P0-1 field.
    """
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SearchService unavailable",
                "message": "The search service failed to initialize. Check server logs.",
                "retry_after_seconds": 30,
                "retry_after": 30,  # legacy alias, do not remove
                "service": "search",
                "degraded_services": _degraded_services_list(request),
                "troubleshooting": [
                    "Verify Qdrant is running and accessible",
                    "Check QDRANT_URL environment variable",
                    "Review application startup logs for errors",
                ],
            },
        )
    # Lazy import for type cast only — zero cost after first import
    from backend.services.search.search_service import SearchService
    return cast(SearchService, service)


def get_ai_client(request: Request) -> Any:
    """
    Get AI client or fail with clear error.

    Raises:
        HTTPException 503: If AI service not initialized. Detail follows
        the P0-1 structured contract (see ``get_search_service``).
    """
    ai_client = getattr(request.app.state, "ai_client", None)
    if ai_client is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service unavailable",
                "message": "The AI service failed to initialize. Check API keys and configuration.",
                "retry_after_seconds": 60,
                "retry_after": 60,  # legacy alias, do not remove
                "service": "ai",
                "degraded_services": _degraded_services_list(request),
                "troubleshooting": [
                    "Verify OPENAI_API_KEY or GOOGLE_API_KEY is set",
                    "Check API key validity and quota",
                    "Review application startup logs for errors",
                ],
            },
        )
    from backend.llm.zantara_ai_client import ZantaraAIClient
    return cast(ZantaraAIClient, ai_client)


def get_intelligent_router(request: Request) -> Any:
    """
    Dependency injection for Intelligent Router.

    Raises:
        HTTPException 503: If router not initialized
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
    from backend.services.routing.intelligent_router import IntelligentRouter
    return cast(IntelligentRouter, router)


def get_memory_service(request: Request) -> Any:
    """
    Dependency injection for Memory Service.

    Raises:
        HTTPException 503: If memory service not initialized
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
    from backend.services.memory import MemoryServicePostgres
    return cast(MemoryServicePostgres, memory_service)


def get_cache(request: Request) -> Any:
    """
    Dependency injection for CacheService.

    Tries app.state first, falls back to singleton.

    Returns:
        CacheService instance
    """
    from backend.core.cache import CacheService

    cache_service = getattr(request.app.state, "cache_service", None)
    if cache_service is not None:
        return cast(CacheService, cache_service)

    # Fallback to singleton (for backward compatibility)
    return get_cache_service()



def get_channel_router(request: Request) -> Any:
    """
    Get ChannelRouter for multi-channel architecture.

    Raises:
        HTTPException 503: If channel router not initialized
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
