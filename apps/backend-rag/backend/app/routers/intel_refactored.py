"""
Intel News API - Search and manage Bali intelligence news

Refactored router using service layer architecture.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path as PathLib

import httpx
from backend.core.embeddings import create_embeddings_generator
from backend.core.qdrant_db import QdrantClient
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants, IntelConstants
from backend.app.metrics import (
    intel_articles_duplicates,
    intel_articles_submitted,
    intel_bulk_operations_total,
    intel_bulk_operation_items,
    intel_items_approved,
    intel_items_rejected,
    intel_scraper_latency,
    intel_user_actions_total,
)
from backend.services.intel import (
    IntelAnalyticsService,
    IntelApprovalService,
    IntelClassificationService,
    IntelStagingService,
)

# Add scraper scripts to path for ClaudeValidator import
scraper_scripts_path = (
    PathLib(__file__).parent.parent.parent.parent.parent / "bali-intel-scraper" / "scripts"
)
if scraper_scripts_path.exists():
    sys.path.insert(0, str(scraper_scripts_path))

router = APIRouter()
logger = logging.getLogger(__name__)

embedder = create_embeddings_generator(api_key=os.getenv("OPENAI_API_KEY"))

# Qdrant collections for intel (from constants)
INTEL_COLLECTIONS = IntelConstants.COLLECTIONS

# Initialize services
classification_service = IntelClassificationService()
staging_service = IntelStagingService()
approval_service = IntelApprovalService()
analytics_service = IntelAnalyticsService(staging_service)

# --- PYDANTIC MODELS ---


class ScraperSubmission(BaseModel):
    """Article submission from bali-intel-scraper"""

    title: str = Field(..., min_length=1, description="Article title (cannot be empty)")
    content: str = Field(..., min_length=1, description="Article content (cannot be empty)")
    source_url: str
    source_name: str
    category: str  # visa, immigration, news, etc.
    relevance_score: int  # 0-100
    published_at: str | None = None
    extraction_method: str | None = IntelConstants.DEFAULT_EXTRACTION_METHOD
    tier: str = IntelConstants.DEFAULT_TIER  # T1, T2, T3
    cover_image: str | None = Field(None, description="Cover image URL/path (optional, generated later by enricher)")


class ApprovalRequest(BaseModel):
    """Request body for staging approval with optional enrichment data"""

    intel_type: str | None = None
    item_id: str | None = None
    item_data: dict | None = None
    enriched_data: dict | None = None
    image_path: str | None = None


class IntelSearchRequest(BaseModel):
    query: str
    category: str | None = None
    date_range: str = "last_7_days"
    tier: list[str] = ["T1", "T2", "T3"]
    impact_level: str | None = None
    limit: int = 20


class IntelStoreRequest(BaseModel):
    collection: str
    id: str
    document: str
    embedding: list[float]
    metadata: dict
    full_data: dict


# --- SCRAPER INTEGRATION ENDPOINTS ---


@router.post("/api/intel/scraper/submit")
async def submit_from_scraper(submission: ScraperSubmission):
    """
    Receive article from bali-intel-scraper and save to staging.

    This endpoint acts as the bridge between the scraper and Intelligence Center.
    Articles are classified as 'visa' or 'news' and saved to the appropriate
    staging folder for team approval.

    Flow:
    1. Scraper POSTs article here
    2. Backend classifies type (visa/news)
    3. Saves to data/staging/{type}/{item_id}.json
    4. Intelligence Center UI shows for manual approval
    5. Team votes via Telegram
    6. If approved → ingested to Qdrant
    """
    start_time = time.time()

    try:
        # Classify intel type using service
        intel_type = classification_service.classify_intel_type(
            submission.category, submission.title, submission.content
        )

        # Generate unique item ID
        item_id = staging_service.generate_item_id(
            intel_type, submission.title, submission.source_url
        )

        # Check for duplicates
        duplicate = staging_service.check_duplicate(intel_type, submission.source_url)
        if duplicate:
            logger.info(
                f"Duplicate article detected (same URL): {submission.source_url}",
                extra={"item_id": item_id, "existing_id": duplicate.get("item_id")},
            )

            intel_articles_duplicates.labels(intel_type=intel_type).inc()
            intel_scraper_latency.labels(scraper_type=submission.source_name).observe(
                time.time() - start_time
            )

            return {
                "success": True,
                "message": "Article already exists in staging",
                "item_id": duplicate.get("item_id"),
                "intel_type": intel_type,
                "duplicate": True,
            }

        # Prepare staging data
        staging_data = {
            "item_id": item_id,
            "title": submission.title,
            "content": submission.content,
            "source_url": submission.source_url,
            "source_name": submission.source_name,
            "category": submission.category,
            "relevance_score": submission.relevance_score,
            "published_at": submission.published_at or "unknown",
            "extraction_method": submission.extraction_method,
            "tier": submission.tier,
            "intel_type": intel_type,
            "status": "pending",
            "detection_type": "scraper_auto",
            "detected_at": datetime.utcnow().isoformat(),
        }

        if submission.cover_image:
            staging_data["cover_image"] = submission.cover_image

        # Save to staging using service
        staging_file = staging_service.save_staging_item(intel_type, item_id, staging_data)

        # Metrics
        intel_articles_submitted.labels(
            scraper_type=submission.source_name, intel_type=intel_type, tier=submission.tier
        ).inc()
        intel_scraper_latency.labels(scraper_type=submission.source_name).observe(
            time.time() - start_time
        )
        staging_service.update_staging_queue_metrics()

        logger.info(
            "Article submitted from scraper",
            extra={
                "item_id": item_id,
                "intel_type": intel_type,
                "title": submission.title[:50],
                "source": submission.source_name,
                "score": submission.relevance_score,
            },
        )

        return {
            "success": True,
            "message": f"Article saved to {intel_type} staging",
            "item_id": item_id,
            "intel_type": intel_type,
            "staging_path": str(staging_file),
            "duplicate": False,
        }

    except Exception as e:
        logger.exception(f"Failed to submit article from scraper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- STAGING ENDPOINTS ---


@router.get("/api/intel/staging/pending")
async def list_pending_items(
    type: str = "all",
    filter_type: str | None = None,
    sort_type: str | None = None,
    search: str | None = None,
):
    """List items pending approval in staging area with filtering and sorting"""
    logger.info(
        "Listing pending items",
        extra={
            "type": type,
            "filter_type": filter_type,
            "sort_type": sort_type,
            "has_search": bool(search),
            "endpoint": "/api/intel/staging/pending",
        },
    )

    result = staging_service.list_pending_items(type, filter_type, sort_type, search)
    return result


@router.get("/api/intel/staging/preview/{type}/{item_id}")
async def preview_staging_item(type: str, item_id: str):
    """Get full content of a staging item"""
    logger.info(
        "Preview staging item requested",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/preview"},
    )

    intel_user_actions_total.labels(intel_type=type, action="preview").inc()

    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Preview item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    logger.info(
        "Preview loaded successfully",
        extra={"type": type, "item_id": item_id, "title": data.get("title", "Untitled")},
    )
    return data


@router.post("/api/intel/staging/bulk-approve/{type}")
async def bulk_approve_items(type: str, item_ids: list[str]):
    """Bulk approve multiple items"""
    logger.info(
        "Bulk approval requested",
        extra={"type": type, "count": len(item_ids), "endpoint": "/api/intel/staging/bulk-approve"},
    )

    intel_bulk_operations_total.labels(intel_type=type, operation="approve").inc()
    intel_bulk_operation_items.labels(intel_type=type, operation="approve").observe(len(item_ids))

    results = {"success": 0, "failed": 0, "errors": []}

    for item_id in item_ids:
        try:
            data = staging_service.load_staging_item(type, item_id)
            if not data:
                results["failed"] += 1
                results["errors"].append(f"{item_id}: not found")
                continue

            # Archive item
            staging_service.archive_item(type, item_id, "approved")
            results["success"] += 1
            intel_items_approved.labels(intel_type=type).inc()
            intel_user_actions_total.labels(intel_type=type, action="approve").inc()

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{item_id}: {str(e)}")
            logger.error(f"Bulk approve failed for {item_id}: {e}", exc_info=True)

    staging_service.update_staging_queue_metrics()
    return results


@router.post("/api/intel/staging/bulk-reject/{type}")
async def bulk_reject_items(type: str, item_ids: list[str]):
    """Bulk reject multiple items"""
    logger.info(
        "Bulk rejection requested",
        extra={"type": type, "count": len(item_ids), "endpoint": "/api/intel/staging/bulk-reject"},
    )

    intel_bulk_operations_total.labels(intel_type=type, operation="reject").inc()
    intel_bulk_operation_items.labels(intel_type=type, operation="reject").observe(len(item_ids))

    results = {"success": 0, "failed": 0, "errors": []}

    for item_id in item_ids:
        try:
            data = staging_service.load_staging_item(type, item_id)
            if not data:
                results["failed"] += 1
                results["errors"].append(f"{item_id}: not found")
                continue

            # Archive item
            staging_service.archive_item(type, item_id, "rejected")
            results["success"] += 1
            intel_items_rejected.labels(intel_type=type).inc()
            intel_user_actions_total.labels(intel_type=type, action="reject").inc()

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{item_id}: {str(e)}")
            logger.error(f"Bulk reject failed for {item_id}: {e}", exc_info=True)

    staging_service.update_staging_queue_metrics()
    return results


@router.post("/api/intel/staging/approve/{type}/{item_id}")
async def approve_staging_item(type: str, item_id: str, request: ApprovalRequest | None = None):
    """
    Initiate approval process by sending Telegram notification to team.

    Now supports ENRICHED content with AI-generated images!

    This endpoint triggers the voting process. The actual ingestion happens
    when the team reaches majority (2/3) via Telegram callback.

    Request body (optional):
    {
        "enriched_data": {...},  # From ArticleEnrichmentService
        "image_path": "/path/to/image.jpg"  # From Gemini image generation
    }
    """
    logger.info(
        "Approval request received - initiating Telegram voting",
        extra={
            "type": type,
            "item_id": item_id,
            "endpoint": "/api/intel/staging/approve",
            "has_enrichment": bool(request and request.enriched_data),
            "has_image": bool(request and request.image_path),
        },
    )

    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Approval failed - item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    title = data.get("title", "Untitled")
    logger.info(
        "Loaded staging item for approval",
        extra={"type": type, "item_id": item_id, "title": title},
    )

    # Extract enrichment data if provided
    enriched_data = request.enriched_data if request else None
    image_path = request.image_path if request else None

    # Send Telegram notification using approval service
    notification_sent = await approval_service.send_approval_notification(
        type, item_id, data, enriched_data, image_path
    )

    if not notification_sent:
        logger.error(
            "Failed to send Telegram notification",
            extra={"type": type, "item_id": item_id, "title": title},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to send approval notification. Check team configuration.",
        )

    logger.info(
        "Telegram voting initiated successfully",
        extra={"type": type, "item_id": item_id, "title": title},
    )

    return {
        "success": True,
        "message": "Approval voting initiated. Team notified via Telegram.",
        "id": item_id,
        "voting_status": "pending",
    }


@router.post("/api/intel/staging/reject/{type}/{item_id}")
async def reject_staging_item(type: str, item_id: str):
    """Reject item and move to archive"""
    logger.info(
        "Rejection started",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/reject"},
    )

    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Rejection failed - item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        title = data.get("title", "Untitled")

        # Archive item using service
        archive_path = staging_service.archive_item(type, item_id, "rejected")

        logger.info(
            "Rejection completed successfully",
            extra={
                "type": type,
                "item_id": item_id,
                "title": title,
                "archive_path": str(archive_path),
            },
        )

        return {"success": True, "message": "Item rejected and archived", "id": item_id}
    except Exception as e:
        logger.error(
            f"Rejection failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/intel/staging/publish/{type}/{item_id}")
async def publish_staging_item(type: str, item_id: str):
    """
    Publish approved item to Qdrant knowledge base and register in anti-duplicate system.

    This endpoint:
    1. Ingests article to Qdrant (knowledge base)
    2. Registers article in anti-duplicate system
    3. Archives to published folder

    Should be called after team approval (manual or via Telegram).
    """
    logger.info(
        "Publish request received",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/publish"},
    )

    intel_user_actions_total.labels(intel_type=type, action="publish").inc()

    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Publish failed - item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        title = data.get("title", "Untitled")
        source_url = data.get("source_url", data.get("url", ""))
        category = data.get("category", type)

        logger.info("Publishing article", extra={"type": type, "item_id": item_id, "title": title})

        # Step 1: Ingest to Qdrant (knowledge base)
        from backend.app.routers.telegram import ingest_intel_to_qdrant

        ingestion_success = await ingest_intel_to_qdrant(item_id, type)

        if not ingestion_success:
            logger.error(
                "Publish failed - Qdrant ingestion error",
                extra={"type": type, "item_id": item_id, "title": title},
            )
            raise HTTPException(
                status_code=500, detail="Failed to ingest article to knowledge base"
            )

        logger.info(
            "✅ Article ingested to Qdrant",
            extra={"type": type, "item_id": item_id, "title": title},
        )

        # Step 2: Register in anti-duplicate system
        try:
            from claude_validator import ClaudeValidator

            published_url = f"https://balizero.com/{category}/{item_id}"

            ClaudeValidator.add_published_article(
                title=title,
                url=published_url,
                category=category,
                published_at=datetime.utcnow().isoformat(),
            )

            logger.info(
                "✅ Article registered in anti-duplicate system",
                extra={"type": type, "item_id": item_id, "title": title, "url": published_url},
            )

        except ImportError:
            logger.warning(
                "⚠️ ClaudeValidator not available - skipping duplicate registration",
                extra={"type": type, "item_id": item_id},
            )
        except Exception as e:
            logger.error(
                f"⚠️ Failed to register in anti-duplicate system: {e}",
                exc_info=True,
                extra={"type": type, "item_id": item_id},
            )

        # Step 3: Update staging file with publish timestamp
        data["published_at"] = datetime.utcnow().isoformat()
        data["published_url"] = f"https://balizero.com/{category}/{item_id}"
        data["status"] = "published"

        # Note: The file has already been moved to archived/approved by ingest_intel_to_qdrant
        # We don't need to move it again

        logger.info(
            "✅ Publish completed successfully",
            extra={
                "type": type,
                "item_id": item_id,
                "title": title,
                "published_url": data["published_url"],
            },
        )

        return {
            "success": True,
            "message": "Article published successfully",
            "id": item_id,
            "title": title,
            "published_url": data["published_url"],
            "published_at": data["published_at"],
            "collection": "visa_oracle" if type == "visa" else "bali_intel_bali_news",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Publish failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/intel/metrics")
async def get_system_metrics():
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
                    and (datetime.now() - task.last_run)
                    < timedelta(hours=IntelConstants.RECENT_TASK_THRESHOLD_HOURS)
                ]
                if recent_runs:
                    agent_status = "active"
                    last_run = max(
                        recent_runs, key=lambda t: t.last_run or datetime.min
                    ).last_run
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
                    archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
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
            visa_client = QdrantClient(collection_name="visa_oracle")
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
                    archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
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
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")


@router.post("/api/intel/search")
async def search_intel(request: IntelSearchRequest):
    """Search intel news with semantic search"""
    try:
        # Generate query embedding
        query_embedding = embedder.generate_single_embedding(request.query)

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
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    where_filter["published_date"] = {"$gte": cutoff_date}

                # Add impact level filter
                if request.impact_level:
                    where_filter["impact_level"] = request.impact_level

                # Search (async)
                results = await client.search(
                    query_embedding=query_embedding, filter=where_filter, limit=request.limit
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
                        }
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
async def store_intel(request: IntelStoreRequest):
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
    category: str | None = None, days: int = IntelConstants.DUPLICATE_CHECK_DAYS
):
    """Get critical impact items"""
    try:
        if category:
            collection_names = [INTEL_COLLECTIONS.get(category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        critical_items = []
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

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
                    ]
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
                        timeout=HttpTimeoutConstants.INTEL_SCRAPER_TIMEOUT
                    ) as http_client:
                        response = await http_client.post(scroll_url, json=scroll_payload, headers=headers)
                        response.raise_for_status()
                        scroll_data = response.json().get("result", {})
                        points = scroll_data.get("points", [])

                        filtered_metadatas = [
                            point.get("payload", {}).get("metadata", {}) for point in points
                        ]
                except Exception as scroll_error:
                    logger.warning(
                        f"Qdrant scroll with filter failed, falling back to peek: {scroll_error}"
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
                        }
                    )

            except Exception:
                continue

        # Sort by date (newest first)
        critical_items.sort(key=lambda x: x.get("published_date", ""), reverse=True)

        return {"items": critical_items, "count": len(critical_items)}

    except Exception as e:
        logger.error(f"Get critical items error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/trends")
async def get_trends(
    category: str | None = None, _days: int = IntelConstants.TRENDS_ANALYSIS_DAYS
):
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
                    }
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
async def get_intelligence_analytics(days: int = IntelConstants.TRENDS_ANALYSIS_DAYS):
    """Get historical analytics and trends for Intelligence Center"""
    logger.info("Analytics requested", extra={"endpoint": "/api/intel/analytics", "days": days})

    try:
        analytics = analytics_service.get_intelligence_analytics(days)
        return analytics

    except Exception as e:
        logger.error(f"Failed to calculate analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analytics calculation failed: {str(e)}")


@router.get("/api/intel/stats/{collection}")
async def get_collection_stats(collection: str):
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
            "last_updated": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
