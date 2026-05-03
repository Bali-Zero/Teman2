"""
Performance Optimization API Router
Exposes PerformanceMonitor and cache management via REST API endpoints
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.services.misc.performance_optimizer import (
    embedding_cache,
    perf_monitor,
    search_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/metrics")
async def get_performance_metrics() -> dict[str, Any]:
    """Get performance metrics"""
    try:
        metrics = perf_monitor.get_metrics()
        return {"success": True, "metrics": metrics}
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clear-cache")
async def clear_caches() -> dict[str, Any]:
    """Clear all caches"""
    try:
        await embedding_cache.clear()
        await search_cache.clear()
        return {"success": True, "status": "caches_cleared"}
    except Exception as e:
        logger.error(f"Failed to clear caches: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clear-cache/embedding")
async def clear_embedding_cache() -> dict[str, Any]:
    """Clear embedding cache only"""
    try:
        await embedding_cache.clear()
        return {"success": True, "status": "embedding_cache_cleared"}
    except Exception as e:
        logger.error(f"Failed to clear embedding cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clear-cache/search")
async def clear_search_cache() -> dict[str, Any]:
    """Clear search cache only"""
    try:
        await search_cache.clear()
        return {"success": True, "status": "search_cache_cleared"}
    except Exception as e:
        logger.error(f"Failed to clear search cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics"""
    try:
        embedding_stats = {
            "size": len(embedding_cache.cache) if hasattr(embedding_cache, "cache") else 0,
            "hits": getattr(embedding_cache, "hits", 0),
            "misses": getattr(embedding_cache, "misses", 0),
        }
        search_stats = {
            "size": len(search_cache.cache) if hasattr(search_cache, "cache") else 0,
            "hits": getattr(search_cache, "hits", 0),
            "misses": getattr(search_cache, "misses", 0),
        }
        return {
            "success": True,
            "embedding_cache": embedding_stats,
            "search_cache": search_stats,
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
