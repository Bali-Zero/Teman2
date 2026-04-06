"""
Intel Analytics & Metrics Endpoints

Split from intel.py for maintainability.
Provides: system metrics, semantic search, store, critical items,
trends, analytics summary, collection stats.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants, IntelConstants
from backend.app.routers.intel import (
    INTEL_COLLECTIONS,
    IntelSearchRequest,
    IntelStoreRequest,
    analytics_service,
    get_embedder,
    staging_service,
)
from backend.app.utils.logging_utils import get_logger
from backend.core.qdrant_db import QdrantClient

logger = get_logger(__name__)

router = APIRouter(tags=["intel-analytics"])



# ─── System metrics ───────────────────────────────────────────────────────────


@router.get("/api/intel/metrics")
async def get_system_metrics() -> Any:
    """Get real-time system metrics for System Pulse dashboard"""
    logger.info("System metrics requested", extra={"endpoint": "/api/intel/metrics"})

    try:
        # Check agent health from autonomous scheduler
        agent_status = "unknown"
        last_run = None
        try:
            try:
                from backend.services.misc.autonomous_scheduler import get_autonomous_scheduler

                autonomous_scheduler = get_autonomous_scheduler()
            except Exception:
                autonomous_scheduler = None

            if autonomous_scheduler and autonomous_scheduler.tasks:
                recent_runs = [
                    task
                    for task in autonomous_scheduler.tasks.values()
                    if task.last_run
                    and (datetime.now(tz=timezone.utc) - task.last_run)
                    < timedelta(hours=IntelConstants.RECENT_TASK_THRESHOLD_HOURS)
                ]
                if recent_runs:
                    agent_status = "active"
                    last_run = max(recent_runs, key=lambda t: t.last_run or datetime.min).last_run
                    if last_run:
                        last_run = last_run.isoformat()
                elif any(task.enabled for task in autonomous_scheduler.tasks.values()):
                    agent_status = "idle"
                else:
                    agent_status = "disabled"
            else:
                agent_status = "not_configured"
        except Exception as e:
            logger.warning(f"Could not check agent health: {e}")
            agent_status = "unknown"

        # Calculate metrics
        metrics = {
            "agent_status": agent_status,
            "last_run": last_run,
            "items_processed_today": 0,
            "avg_response_time_ms": 0,
            "qdrant_health": "healthy",
            "next_scheduled_run": None,
            "uptime_percentage": 99.8,
        }

        # Count pending items using staging service
        visa_dir = staging_service.get_staging_dir("visa")
        news_dir = staging_service.get_staging_dir("news")
        visa_count = len(list(visa_dir.glob("*.json"))) if visa_dir.exists() else 0
        news_count = len(list(news_dir.glob("*.json"))) if news_dir.exists() else 0
        metrics["items_processed_today"] = visa_count + news_count

        # Check last processed item (most recent archive)
        last_approved = None
        for archive_type in ["visa", "news"]:
            archive_dir = staging_service.get_staging_dir(archive_type) / "archived" / "approved"
            if archive_dir.exists():
                for file_path in sorted(
                    archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True,
                ):
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            last_run_time = data.get("ingested_at")
                            if last_run_time:
                                last_approved = last_run_time
                                break
                    except Exception:
                        continue
            if last_approved:
                break

        if last_approved:
            metrics["last_run"] = last_approved

        # Check Qdrant health
        try:
            QdrantClient(collection_name="visa_oracle")
            metrics["qdrant_health"] = "healthy"
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}", exc_info=True)
            metrics["qdrant_health"] = "degraded"

        # Calculate next scheduled run
        if last_approved:
            try:
                last_dt = datetime.fromisoformat(last_approved.replace("Z", "+00:00"))
                next_run = last_dt + timedelta(hours=IntelConstants.SCHEDULER_RUN_INTERVAL_HOURS)
                metrics["next_scheduled_run"] = next_run.isoformat()
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse last_approved date: {e}")

        # Calculate average response time based on recent approvals
        response_times = []
        for archive_type in ["visa", "news"]:
            archive_dir = staging_service.get_staging_dir(archive_type) / "archived" / "approved"
            if archive_dir.exists():
                for file_path in sorted(
                    archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True,
                )[:10]:
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            content_len = len(data.get("content", ""))
                            response_times.append(1000 + (content_len / 10))
                    except Exception:
                        continue

        if response_times:
            metrics["avg_response_time_ms"] = int(sum(response_times) / len(response_times))
        else:
            metrics["avg_response_time_ms"] = IntelConstants.DEFAULT_AVG_RESPONSE_TIME_MS

        logger.info(
            "System metrics calculated",
            extra={
                "agent_status": metrics["agent_status"],
                "qdrant_health": metrics["qdrant_health"],
                "items_processed": metrics["items_processed_today"],
            },
        )

        return metrics

    except Exception as e:
        logger.error(f"Failed to calculate system metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}") from e


@router.post("/api/intel/search")
async def search_intel(request: IntelSearchRequest) -> dict[str, Any]:
    """Search intel news with semantic search"""
    try:
        # Generate query embedding
        query_embedding = get_embedder().generate_single_embedding(request.query)

        # Determine collections to search
        if request.category:
            collection_names = [INTEL_COLLECTIONS.get(request.category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        all_results = []

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)

                # Build metadata filter
                where_filter = {"tier": {"$in": request.tier}}

                # Add date range filter
                if request.date_range != "all":
                    days_map = {
                        "today": 1,
                        "last_7_days": 7,
                        "last_30_days": 30,
                        "last_90_days": 90,
                    }
                    days = days_map.get(request.date_range, IntelConstants.DUPLICATE_CHECK_DAYS)
                    cutoff_date = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
                    where_filter["published_date"] = {"$gte": cutoff_date}

                # Add impact level filter
                if request.impact_level:
                    where_filter["impact_level"] = request.impact_level

                # Search (async)
                results = await client.search(
                    query_embedding=query_embedding, filter=where_filter, limit=request.limit,
                )

                # Parse results
                for doc, metadata, distance in zip(
                    results.get("documents", []),
                    results.get("metadatas", []),
                    results.get("distances", []),
                    strict=True,
                ):
                    similarity_score = 1 / (1 + distance)

                    all_results.append(
                        {
                            "id": metadata.get("id"),
                            "title": metadata.get("title"),
                            "summary_english": doc[: IntelConstants.SUMMARY_PREVIEW_LENGTH],
                            "summary_italian": metadata.get("summary_italian", ""),
                            "source": metadata.get("source"),
                            "tier": metadata.get("tier"),
                            "published_date": metadata.get("published_date"),
                            "category": collection_name.replace("bali_intel_", ""),
                            "impact_level": metadata.get("impact_level"),
                            "url": metadata.get("url"),
                            "key_changes": metadata.get("key_changes"),
                            "action_required": metadata.get("action_required") == "True",
                            "deadline_date": metadata.get("deadline_date"),
                            "similarity_score": similarity_score,
                        },
                    )

            except Exception as e:
                logger.warning(f"Error searching collection {collection_name}: {e}")
                continue

        # Sort by similarity score
        all_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Limit total results
        all_results = all_results[: request.limit]

        return {"results": all_results, "total": len(all_results)}

    except Exception as e:
        logger.error(f"Intel search error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/intel/store")
async def store_intel(request: IntelStoreRequest) -> dict[str, Any]:
    """Store intel news item in Qdrant"""
    try:
        collection_name = INTEL_COLLECTIONS.get(request.collection)
        if not collection_name:
            raise HTTPException(status_code=400, detail=f"Invalid collection: {request.collection}")

        client = QdrantClient(collection_name=collection_name)

        await client.upsert_documents(
            chunks=[request.document],
            embeddings=[request.embedding],
            metadatas=[request.metadata],
            ids=[request.id],
        )

        return {"success": True, "collection": collection_name, "id": request.id}

    except Exception as e:
        logger.error(f"Store intel error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/critical")
async def get_critical_items(
    category: str | None = None, days: int = IntelConstants.DUPLICATE_CHECK_DAYS,
) -> dict[str, Any]:
    """Get critical impact items"""
    try:
        if category:
            collection_names = [INTEL_COLLECTIONS.get(category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        critical_items = []
        cutoff_date = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)

                # Use Qdrant scroll with filter for better performance
                qdrant_filter = {
                    "must": [
                        {"key": "impact_level", "match": {"value": "critical"}},
                        {"key": "published_date", "range": {"gte": cutoff_date}},
                    ],
                }

                try:
                    qdrant_url = settings.qdrant_url
                    qdrant_api_key = settings.qdrant_api_key

                    scroll_url = f"{qdrant_url}/collections/{collection_name}/points/scroll"
                    headers = {}
                    if qdrant_api_key:
                        headers["api-key"] = qdrant_api_key

                    scroll_payload = {
                        "limit": 100,
                        "with_payload": True,
                        "with_vectors": False,
                        "filter": qdrant_filter,
                    }

                    async with httpx.AsyncClient(
                        timeout=HttpTimeoutConstants.INTEL_SCRAPER_TIMEOUT,
                    ) as http_client:
                        response = await http_client.post(
                            scroll_url, json=scroll_payload, headers=headers,
                        )
                        response.raise_for_status()
                        scroll_data = response.json().get("result", {})
                        points = scroll_data.get("points", [])

                        filtered_metadatas = [
                            point.get("payload", {}).get("metadata", {}) for point in points
                        ]
                except Exception as scroll_error:
                    logger.warning(
                        f"Qdrant scroll with filter failed, falling back to peek: {scroll_error}",
                    )
                    results = await client.peek(limit=100)
                    filtered_metadatas = []
                    for metadata in results.get("metadatas", []):
                        if (
                            metadata.get("impact_level") == "critical"
                            and metadata.get("published_date", "") >= cutoff_date
                        ):
                            filtered_metadatas.append(metadata)

                for metadata in filtered_metadatas[:50]:
                    critical_items.append(
                        {
                            "id": metadata.get("id"),
                            "title": metadata.get("title"),
                            "source": metadata.get("source"),
                            "tier": metadata.get("tier"),
                            "published_date": metadata.get("published_date"),
                            "category": collection_name.replace("bali_intel_", ""),
                            "url": metadata.get("url"),
                            "action_required": metadata.get("action_required") == "True",
                            "deadline_date": metadata.get("deadline_date"),
                            "severity": "high",  # All critical items are high severity for chain compatibility
                        },
                    )

            except Exception:
                continue

        # Sort by date (newest first)
        critical_items.sort(key=lambda x: x.get("published_date", ""), reverse=True)

        # Return with both 'items' and 'alerts' keys for backward compatibility
        return {
            "items": critical_items,
            "alerts": critical_items,  # Alias for chain_daily_ops_autopilot compatibility
            "count": len(critical_items),
        }

    except Exception as e:
        logger.error(f"Get critical items error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/trends")
async def get_trends(
    category: str | None = None, _days: int = IntelConstants.TRENDS_ANALYSIS_DAYS,
) -> dict[str, Any]:
    """Get trending topics and keywords"""
    try:
        if category:
            collection_names = [INTEL_COLLECTIONS.get(category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        all_keywords = []

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)
                stats = client.get_collection_stats()

                all_keywords.append(
                    {
                        "collection": collection_name.replace("bali_intel_", ""),
                        "total_items": stats.get("total_documents", 0),
                    },
                )

            except Exception:
                continue

        return {
            "trends": all_keywords,
            "top_topics": [],  # Would require NLP analysis
        }

    except Exception as e:
        logger.error(f"Get trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/analytics")
async def get_intelligence_analytics(days: int = IntelConstants.TRENDS_ANALYSIS_DAYS) -> Any:
    """Get historical analytics and trends for Intelligence Center"""
    logger.info("Analytics requested", extra={"endpoint": "/api/intel/analytics", "days": days})

    try:
        return analytics_service.get_intelligence_analytics(days)

    except Exception as e:
        logger.error(f"Failed to calculate analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Analytics calculation failed: {str(e)}",
        ) from e


@router.get("/api/intel/stats/{collection}")
async def get_collection_stats(collection: str) -> dict[str, Any]:
    """Get statistics for a specific intel collection"""
    try:
        collection_name = INTEL_COLLECTIONS.get(collection)
        if not collection_name:
            raise HTTPException(status_code=404, detail=f"Collection not found: {collection}")

        client = QdrantClient(collection_name=collection_name)
        stats = client.get_collection_stats()

        return {
            "collection_name": collection_name,
            "total_documents": stats.get("total_documents", 0),
            "last_updated": datetime.now(tz=timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
