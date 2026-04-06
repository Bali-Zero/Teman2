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


def get_search_service(request: Request) -> Any:
    """
    Dependency injection for SearchService.

    Raises:
        HTTPException 503: If service not initialized
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
    # Lazy import for type cast only — zero cost after first import
    from backend.services.search.search_service import SearchService
    return cast(SearchService, service)


def get_ai_client(request: Request) -> Any:
    """
    Get AI client or fail with clear error.

    Raises:
        HTTPException 503: If AI service not initialized
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
