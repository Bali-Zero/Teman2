"""
Intel News API - Search and manage Bali intelligence news

Refactored router using service layer architecture.
"""

import asyncio
import base64
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path as PathLib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.constants import IntelConstants
from backend.app.metrics import (
    intel_bulk_operation_items,
    intel_bulk_operations_total,
    intel_items_approved,
    intel_items_rejected,
    intel_user_actions_total,
)
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.core.embeddings import create_embeddings_generator
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
    cover_image: str | None = Field(
        None, description="Cover image URL/path (optional, generated later by enricher)",
    )
    cover_image_base64: str | None = Field(
        None, description="Cover image as base64 string (uploaded to Drive on submit)",
    )


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


class EditStagingItemRequest(BaseModel):
    """Request body for editing staging item"""

    title: str | None = None
    content: str | None = None
    category: str | None = None


class CoverImageUploadRequest(BaseModel):
    """Request body for cover image upload"""

    cover_image_base64: str = Field(..., description="Base64 encoded image")
    cover_image_filename: str | None = Field(None, description="Image filename (optional)")


class RegisterNotificationRequest(BaseModel):
    """Register Telegram message_id → staging item mapping for cover image uploads."""

    telegram_message_id: int = Field(..., description="Telegram message_id sent to Damar")
    chat_id: int = Field(..., description="Damar's Telegram chat_id")
    intel_type: str = Field(..., description="news or visa")
    item_id: str = Field(..., description="Staging item ID")
    title: str = Field("", description="Article title for display")


class PublishToSiteRequest(BaseModel):
    """Optional request body for publish with homepage position."""

    position: str = Field(
        default="latest",
        description="Homepage position: hero_main, hero_2-5, insight_1-3, or latest",
    )


VALID_HOMEPAGE_POSITIONS = {
    "hero_main",
    "hero_2",
    "hero_3",
    "hero_4",
    "hero_5",
    "insight_1",
    "insight_2",
    "insight_3",
}


# HELPER FUNCTIONS & SCRAPER → intel_scraper.py
# ANALYTICS → intel_analytics.py

# --- STAGING ENDPOINTS ---


@router.get("/api/intel/staging/pending")
async def list_pending_items(
    type: str = "all",
    filter_type: str | None = None,
    sort_type: str | None = None,
    search: str | None = None,
) -> Any:
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

    return staging_service.list_pending_items(type, filter_type, sort_type, search)


@router.get("/api/intel/staging/preview/{type}/{item_id}")
async def preview_staging_item(type: str, item_id: str) -> Any:
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
async def bulk_approve_items(type: str, item_ids: list[str]) -> Any:
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
async def bulk_reject_items(type: str, item_ids: list[str]) -> Any:
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
async def approve_staging_item(
    type: str,
    item_id: str,
    request: ApprovalRequest | None = None,
    _api_key_verified=Depends(verify_internal_api_key),
) -> dict[str, Any]:
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
        type, item_id, data, enriched_data, image_path,
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


@router.put("/api/intel/staging/{type}/{item_id}")
async def edit_staging_item(
    type: str, item_id: str, request: EditStagingItemRequest,
) -> dict[str, Any]:
    """
    Edit staging item (title, content, category).

    Only updates provided fields (partial update).
    """
    logger.info(
        "Edit staging item requested",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/edit"},
    )

    intel_user_actions_total.labels(intel_type=type, action="edit").inc()

    # Load existing staging item
    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Edit failed - item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    # Update only provided fields
    updated_fields = {}
    if request.title is not None:
        data["title"] = request.title
        updated_fields["title"] = request.title
    if request.content is not None:
        data["content"] = request.content
        updated_fields["content"] = request.content
    if request.category is not None:
        data["category"] = request.category
        updated_fields["category"] = request.category

    # Save updated staging item
    staging_service.save_staging_item(type, item_id, data)

    logger.info(
        "Edit completed successfully",
        extra={
            "type": type,
            "item_id": item_id,
            "updated_fields": list(updated_fields.keys()),
        },
    )

    return {
        "success": True,
        "message": "Item updated successfully",
        "id": item_id,
        "updated_fields": updated_fields,
    }


@router.post("/api/intel/staging/{type}/{item_id}/cover")
async def upload_cover_image(
    type: str, item_id: str, request: CoverImageUploadRequest,
) -> dict[str, Any]:
    """
    Upload cover image for staging item.

    Saves image to data/staging/{type}/covers/{item_id}.{ext}
    Updates staging JSON with cover_image path.
    """
    logger.info(
        "Cover image upload requested",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/cover"},
    )

    intel_user_actions_total.labels(intel_type=type, action="upload_cover").inc()

    # Load existing staging item
    data = staging_service.load_staging_item(type, item_id)
    if not data:
        logger.warning(
            "Cover upload failed - item not found",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    # Decode base64 image
    try:
        image_data = base64.b64decode(request.cover_image_base64)
    except Exception as e:
        logger.error(
            f"Invalid base64 image: {e}",
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}") from e

    # Determine file extension
    filename = request.cover_image_filename or f"{item_id}.jpg"
    ext = PathLib(filename).suffix or ".jpg"

    # Save cover image
    covers_dir = staging_service.get_staging_dir(type) / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    cover_path = covers_dir / f"{item_id}{ext}"
    cover_path.write_bytes(image_data)

    # Update staging JSON
    data["cover_image"] = str(cover_path.relative_to(staging_service.get_staging_dir(type)))
    staging_service.save_staging_item(type, item_id, data)

    logger.info(
        "Cover image uploaded successfully",
        extra={
            "type": type,
            "item_id": item_id,
            "cover_image_path": str(cover_path),
        },
    )

    return {
        "success": True,
        "message": "Cover image uploaded successfully",
        "id": item_id,
        "cover_image_path": str(cover_path),
        "cover_image_url": f"/api/intel/staging/{type}/{item_id}/cover/preview",
    }


@router.post("/api/intel/staging/reject/{type}/{item_id}")
async def reject_staging_item(type: str, item_id: str) -> dict[str, Any]:
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
            f"Rejection failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

# INGEST & PUBLISH → intel_scraper.py

# ─── Post-publish queue ───────────────────────────────────────────────────────
# In-memory queue (persists across requests, resets on deploy — acceptable for
# this use case since the poller runs every 5 minutes and deploy is rare).
_post_publish_queue: list[dict] = []
_post_publish_lock = asyncio.Lock()


@router.post("/api/intel/post-publish-queue")
async def enqueue_post_publish(request: Request) -> dict:
    """Internal: add a slug to the post-processing queue (translate + image)."""
    body = await request.json()
    slug = body.get("slug", "")
    category = body.get("category", "business")
    if not slug:
        raise HTTPException(status_code=400, detail="slug required")
    async with _post_publish_lock:
        # avoid duplicates
        if not any(item["slug"] == slug for item in _post_publish_queue):
            _post_publish_queue.append(
                {"slug": slug, "category": category, "queued_at": datetime.now(timezone.utc).isoformat()},
            )
    logger.info("📥 Post-publish queue: added", extra={"slug": slug, "category": category})
    return {"ok": True, "slug": slug}


@router.get("/api/intel/post-publish-queue/pending")
async def get_pending_queue(x_api_key: str | None = None, request: Request = None) -> dict:
    """Poller endpoint: returns pending slugs for post-processing."""
    # Simple API key auth
    api_key = (request.headers.get("X-API-Key") if request else None) or x_api_key
    if api_key != settings.intel_scraper_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with _post_publish_lock:
        pending = list(_post_publish_queue)
    return {"pending": pending, "count": len(pending)}


@router.post("/api/intel/post-publish-queue/done")
async def mark_queue_done(request: Request) -> dict:
    """Poller endpoint: mark slugs as processed and remove from queue."""
    api_key = request.headers.get("X-API-Key")
    if api_key != settings.intel_scraper_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    slugs = body.get("slugs", [])
    async with _post_publish_lock:
        global _post_publish_queue
        _post_publish_queue = [item for item in _post_publish_queue if item["slug"] not in slugs]
    logger.info("✅ Post-publish queue: marked done", extra={"slugs": slugs})
    return {"ok": True, "removed": slugs}

# METRICS, SEARCH, TRENDS → intel_analytics.py
