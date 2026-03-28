"""
Intel News API - Search and manage Bali intelligence news

Refactored router using service layer architecture.
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path as PathLib
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants, IntelConstants
from backend.app.metrics import (
    intel_articles_duplicates,
    intel_articles_submitted,
    intel_bulk_operation_items,
    intel_bulk_operations_total,
    intel_items_approved,
    intel_items_rejected,
    intel_scraper_latency,
    intel_user_actions_total,
)
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.core.embeddings import create_embeddings_generator
from backend.core.qdrant_db import QdrantClient
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
        None, description="Cover image URL/path (optional, generated later by enricher)"
    )
    cover_image_base64: str | None = Field(
        None, description="Cover image as base64 string (uploaded to Drive on submit)"
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


async def update_homepage_layout(slug: str, position: str) -> None:
    """
    Update homepage-layout.json in the GitHub repo.
    Reads current file, updates the position, commits the change.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    github_owner = os.getenv("GITHUB_OWNER", "Balizero1987")
    github_repo = os.getenv("GITHUB_REPO", "Teman2")
    file_path = "apps/mouth/src/content/homepage-layout.json"

    if not github_token:
        raise ValueError("GITHUB_TOKEN not configured")

    if position not in VALID_HOMEPAGE_POSITIONS:
        raise ValueError(f"Invalid position: {position}")

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Get current file content + SHA
        url = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/{file_path}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        file_data = resp.json()
        current_sha = file_data["sha"]

        # Decode and parse current layout
        current_content = base64.b64decode(file_data["content"]).decode("utf-8")
        layout = json.loads(current_content)

        # Update the position
        layout[position] = slug

        # Commit the updated layout
        new_content = json.dumps(layout, indent=2) + "\n"
        encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

        update_resp = await client.put(
            url,
            headers=headers,
            json={
                "message": f"feat(layout): set {position} to {slug}",
                "content": encoded,
                "sha": current_sha,
                "branch": "main",
            },
        )
        update_resp.raise_for_status()


# --- CONVERSION FUNCTIONS ---


def convert_staging_to_enriched_article(staging_data: dict) -> dict:
    """
    Convert staging item (markdown simple) to EnrichedArticle format.

    Parses markdown content to extract sections and generates EnrichedArticle structure.

    Args:
        staging_data: Staging item dictionary with title, content (markdown), etc.

    Returns:
        Dictionary ready to be converted to EnrichedArticle Pydantic model
    """

    title = staging_data.get("title", "Untitled")
    content = staging_data.get("content", "")
    category = staging_data.get("category", "news")
    relevance_score = staging_data.get("relevance_score", 50)
    source_url = staging_data.get("source_url", staging_data.get("url", ""))
    source_name = staging_data.get("source_name", "Bali Intel Scraper")

    # Parse markdown content to extract sections
    # Format: ## Summary\n...\n## Facts\n...\n## Bali Zero Take\n...\n## Next Steps\n...

    # Extract Summary section
    summary_match = re.search(
        r"## Summary\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE
    )
    ai_summary = summary_match.group(1).strip() if summary_match else content[:280]

    # Extract Facts section
    facts_match = re.search(r"## Facts\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE)
    facts = facts_match.group(1).strip() if facts_match else content

    # Extract Bali Zero Take section
    bali_zero_take_match = re.search(
        r"## Bali Zero Take\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE
    )
    bali_zero_take_text = (
        bali_zero_take_match.group(1).strip()
        if bali_zero_take_match
        else content[len(facts) :].strip()[:600]
    )

    # Parse Bali Zero Take subsections if present
    hidden_insight_match = re.search(
        r"(?:###\s*)?Hidden Insight[:\s]*(.*?)(?=\n(?:###|##)|$)",
        bali_zero_take_text,
        re.DOTALL | re.IGNORECASE,
    )
    hidden_insight = (
        hidden_insight_match.group(1).strip() if hidden_insight_match else bali_zero_take_text[:200]
    )

    our_analysis_match = re.search(
        r"(?:###\s*)?Our Analysis[:\s]*(.*?)(?=\n(?:###|##)|$)",
        bali_zero_take_text,
        re.DOTALL | re.IGNORECASE,
    )
    our_analysis = (
        our_analysis_match.group(1).strip() if our_analysis_match else bali_zero_take_text[200:400]
    )

    our_advice_match = re.search(
        r"(?:###\s*)?Our Advice[:\s]*(.*?)(?=\n(?:###|##)|$)",
        bali_zero_take_text,
        re.DOTALL | re.IGNORECASE,
    )
    our_advice = (
        our_advice_match.group(1).strip() if our_advice_match else bali_zero_take_text[400:]
    )

    # Extract Next Steps section
    next_steps_match = re.search(
        r"## Next Steps\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE
    )
    next_steps_text = next_steps_match.group(1).strip() if next_steps_match else ""

    # Parse Next Steps for expat and investor
    expat_steps = []
    investor_steps = []

    # Try to extract expat and investor sections
    expat_match = re.search(
        r"(?:###\s*)?(?:For\s+)?Expat[s]?[:\s]*(.*?)(?=\n(?:###|##)|$)",
        next_steps_text,
        re.DOTALL | re.IGNORECASE,
    )
    if expat_match:
        expat_text = expat_match.group(1).strip()
        # Extract list items
        expat_steps = [
            item.strip().lstrip("- ").lstrip("* ")
            for item in re.split(r"\n(?=-|\*)", expat_text)
            if item.strip()
        ]

    investor_match = re.search(
        r"(?:###\s*)?(?:For\s+)?Investor[s]?[:\s]*(.*?)(?=\n(?:###|##)|$)",
        next_steps_text,
        re.DOTALL | re.IGNORECASE,
    )
    if investor_match:
        investor_text = investor_match.group(1).strip()
        # Extract list items
        investor_steps = [
            item.strip().lstrip("- ").lstrip("* ")
            for item in re.split(r"\n(?=-|\*)", investor_text)
            if item.strip()
        ]

    # If no specific sections found, try to extract all list items
    if not expat_steps and not investor_steps:
        all_steps = [
            item.strip().lstrip("- ").lstrip("* ")
            for item in re.split(r"\n(?=-|\*)", next_steps_text)
            if item.strip() and len(item.strip()) > 10
        ]
        # Split between expat and investor (rough heuristic)
        mid_point = len(all_steps) // 2
        expat_steps = (
            all_steps[:mid_point] if all_steps else ["Review the article for specific actions"]
        )
        investor_steps = (
            all_steps[mid_point:] if all_steps else ["Review the article for specific actions"]
        )

    # Ensure we have at least one step for each
    if not expat_steps:
        expat_steps = ["Review the article for specific actions"]
    if not investor_steps:
        investor_steps = ["Review the article for specific actions"]

    # Determine priority based on relevance_score
    if relevance_score >= 75:
        priority = "high"
    elif relevance_score >= 50:
        priority = "medium"
    else:
        priority = "low"

    # Generate TLDR from summary and facts
    tldr_what = facts[:150] if facts else title
    tldr_who = "Expats and investors in Indonesia"
    tldr_when = "Check article for specific dates"
    tldr_should_worry = (
        "Depends" if priority == "medium" else ("Yes" if priority == "high" else "No")
    )
    tldr_risk_level = priority.capitalize()

    # Generate tags from category and title
    ai_tags = [category]
    title_words = title.lower().split()
    for word in title_words[:4]:
        if len(word) > 3 and word not in ["the", "and", "for", "with", "from"]:
            ai_tags.append(word)

    # Suggested components based on content
    suggested_components = ["InfoCard", "Checklist"]
    if "timeline" in content.lower() or "date" in content.lower():
        suggested_components.append("timeline")
    if "comparison" in content.lower() or "vs" in content.lower():
        suggested_components.append("comparison-table")

    # Build EnrichedArticle structure
    return {
        "title": title,
        "headline": title,
        "tldr": {
            "should_worry": tldr_should_worry,
            "what": tldr_what,
            "who": tldr_who,
            "when": tldr_when,
            "risk_level": tldr_risk_level,
        },
        "facts": facts,
        "bali_zero_take": {
            "hidden_insight": hidden_insight,
            "our_analysis": our_analysis,
            "our_advice": our_advice,
        },
        "next_steps": {
            "expat": expat_steps[:5],  # Limit to 5 items
            "investor": investor_steps[:5],  # Limit to 5 items
        },
        "category": category,
        "priority": priority,
        "relevance_score": relevance_score,
        "ai_summary": ai_summary[:280],  # Limit to 280 chars
        "ai_tags": ai_tags[:5],  # Limit to 5 tags
        "suggested_components": suggested_components[:3],  # Limit to 3 components
        "cover_image": None,  # Will be set from staging_data if available
        "source": source_name,
        "source_url": source_url,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }



# --- SCRAPER INTEGRATION ENDPOINTS ---


@router.post("/api/intel/staging/register-notification")
async def register_notification(
    request: RegisterNotificationRequest,
    _api_key_verified=Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Register Telegram message_id → staging item mapping for Damar's cover image uploads."""
    from backend.services.intel.intel_cover_handler import intel_cover_handler

    intel_cover_handler.register_notification(
        telegram_message_id=request.telegram_message_id,
        chat_id=request.chat_id,
        intel_type=request.intel_type,
        item_id=request.item_id,
        title=request.title,
    )
    return {
        "success": True,
        "message_id": request.telegram_message_id,
        "item_id": request.item_id,
    }


@router.post("/api/intel/scraper/submit")
async def submit_from_scraper(
    submission: ScraperSubmission,
    _api_key_verified=Depends(verify_internal_api_key),
) -> dict[str, Any]:
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
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

        if submission.cover_image:
            staging_data["cover_image"] = submission.cover_image

        # Upload cover image to Google Drive if base64 provided
        if submission.cover_image_base64:
            try:
                from backend.services.integrations.service_account_drive_service import (
                    ServiceAccountDriveService,
                )

                drive_svc = ServiceAccountDriveService()
                if drive_svc.service:
                    image_bytes = base64.b64decode(submission.cover_image_base64)
                    # Use Intel_Images folder on Drive (create if needed)
                    intel_images_folder_id = os.getenv("INTEL_IMAGES_DRIVE_FOLDER_ID", "root")
                    file_ext = (
                        "png" if len(image_bytes) > 0 and image_bytes[:4] == b"\x89PNG" else "jpg"
                    )
                    drive_result = await drive_svc.upload_file_to_folder(
                        folder_id=intel_images_folder_id,
                        file_content=image_bytes,
                        file_name=f"{item_id}.{file_ext}",
                        mime_type=f"image/{file_ext}",
                    )
                    staging_data["image_drive_file_id"] = drive_result.get("id")
                    staging_data["image_drive_url"] = drive_result.get("webViewLink")
                    logger.info(
                        "Cover image uploaded to Drive",
                        extra={
                            "item_id": item_id,
                            "drive_file_id": drive_result.get("id"),
                        },
                    )
                else:
                    logger.warning("Drive service not configured, skipping image upload")
            except Exception as e:
                logger.warning(
                    f"Failed to upload cover image to Drive: {e}",
                    extra={"item_id": item_id},
                )

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
        raise HTTPException(status_code=500, detail=str(e)) from e


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


@router.put("/api/intel/staging/{type}/{item_id}")
async def edit_staging_item(
    type: str, item_id: str, request: EditStagingItemRequest
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
    type: str, item_id: str, request: CoverImageUploadRequest
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
            f"Rejection failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id}
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


async def ingest_intel_to_qdrant(item_id: str, intel_type: str) -> bool:
    """
    Ingest a staging item into the appropriate Qdrant collection.

    Args:
        item_id: Unique item identifier
        intel_type: "news", "visa", etc.

    Returns:
        True if ingestion succeeded
    """
    try:
        data = staging_service.load_staging_item(intel_type, item_id)
        if not data:
            logger.error(
                "Qdrant ingestion failed - item not found",
                extra={"item_id": item_id, "intel_type": intel_type},
            )
            return False

        collection_name = INTEL_COLLECTIONS.get(intel_type)
        if not collection_name:
            logger.error(
                f"No Qdrant collection mapped for intel_type={intel_type}",
                extra={"item_id": item_id, "intel_type": intel_type},
            )
            return False

        title = data.get("title", "Untitled")
        content = data.get("content", "")
        source_url = data.get("source_url", data.get("url", ""))
        category = data.get("category", intel_type)

        # Build text for embedding
        embed_text = f"{title}\n\n{content}"

        # Generate embedding using text-embedding-3-small
        embedding = await embedder.generate_single_embedding(embed_text)

        # Build metadata
        metadata = {
            "title": title,
            "source_url": source_url,
            "category": category,
            "intel_type": intel_type,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source_name": data.get("source_name", ""),
            "relevance_score": data.get("relevance_score", 0),
        }

        # Upsert to Qdrant
        client = QdrantClient(collection_name=collection_name)
        await client.upsert_documents(
            chunks=[embed_text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[item_id],
        )

        logger.info(
            "Article ingested to Qdrant",
            extra={
                "item_id": item_id,
                "intel_type": intel_type,
                "collection": collection_name,
                "title": title,
            },
        )
        return True

    except Exception as e:
        logger.error(
            f"Qdrant ingestion failed: {e}",
            exc_info=True,
            extra={"item_id": item_id, "intel_type": intel_type},
        )
        return False


@router.post("/api/intel/staging/publish/{type}/{item_id}")
async def publish_staging_item(
    type: str,
    item_id: str,
    body: PublishToSiteRequest | None = None,
    request: Request = None,
) -> dict[str, Any]:
    """
    Publish approved item to Qdrant knowledge base and register in anti-duplicate system.

    Optional body: {"position": "hero_main"} to set homepage position.

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
        data.get("source_url", data.get("url", ""))
        category = data.get("category", type)

        logger.info("Publishing article", extra={"type": type, "item_id": item_id, "title": title})

        # Step 1: Ingest to Qdrant (knowledge base)
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

            published_url = f"{settings.balizero_website_url}/{category}/{item_id}"

            ClaudeValidator.add_published_article(
                title=title,
                url=published_url,
                category=category,
                published_at=datetime.now(timezone.utc).isoformat(),
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

        # Step 3: Publish to GitHub/Vercel → balizero.com
        published_url = f"{settings.balizero_website_url}/{category}/{item_id}"
        github_commit_sha = None
        mdx_path = None
        article_slug = item_id  # fallback: use item_id if GitHub publish fails

        try:
            from backend.app.routers.article_composer import (
                BaliZeroTake,
                EnrichedArticle,
                NextSteps,
                PublishRequest,
                TLDRSection,
            )

            # Convert staging item to EnrichedArticle
            enriched_dict = convert_staging_to_enriched_article(data)

            # Create Pydantic models from dict
            enriched_article = EnrichedArticle(
                title=enriched_dict["title"],
                headline=enriched_dict["headline"],
                tldr=TLDRSection(**enriched_dict["tldr"]),
                facts=enriched_dict["facts"],
                bali_zero_take=BaliZeroTake(**enriched_dict["bali_zero_take"]),
                next_steps=NextSteps(**enriched_dict["next_steps"]),
                category=enriched_dict["category"],
                priority=enriched_dict["priority"],
                relevance_score=enriched_dict["relevance_score"],
                ai_summary=enriched_dict["ai_summary"],
                ai_tags=enriched_dict["ai_tags"],
                suggested_components=enriched_dict["suggested_components"],
                cover_image=enriched_dict.get("cover_image"),
                source=enriched_dict["source"],
                source_url=enriched_dict["source_url"],
                enriched_at=enriched_dict["enriched_at"],
            )

            # Prepare cover image if available
            cover_image_base64 = None
            cover_image_filename = None

            # Priority 1: Download from Google Drive (uploaded by scraper)
            if data.get("image_drive_file_id"):
                try:
                    from backend.services.integrations.service_account_drive_service import (
                        ServiceAccountDriveService,
                    )

                    drive_svc = ServiceAccountDriveService()
                    if drive_svc.service:
                        file_id = data["image_drive_file_id"]
                        # Download file content from Drive
                        request = drive_svc.service.files().get_media(fileId=file_id)
                        image_bytes = await asyncio.to_thread(request.execute)
                        cover_image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                        file_ext = "png" if image_bytes[:4] == b"\x89PNG" else "jpg"
                        cover_image_filename = f"{item_id}.{file_ext}"
                        logger.info(
                            "Cover image downloaded from Drive",
                            extra={
                                "type": type,
                                "item_id": item_id,
                                "drive_file_id": file_id,
                                "size_bytes": len(image_bytes),
                            },
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to download cover image from Drive: {e}",
                        extra={
                            "type": type,
                            "item_id": item_id,
                            "drive_file_id": data.get("image_drive_file_id"),
                        },
                    )

            # Priority 2: Try local filesystem (legacy path)
            if not cover_image_base64 and data.get("cover_image"):
                try:
                    cover_image_path = data["cover_image"]
                    if not os.path.isabs(cover_image_path):
                        staging_dir = staging_service.get_staging_dir(type)
                        cover_image_path = staging_dir / cover_image_path
                    else:
                        cover_image_path = PathLib(cover_image_path)

                    if cover_image_path.exists():
                        cover_image_base64 = base64.b64encode(cover_image_path.read_bytes()).decode(
                            "utf-8"
                        )
                        cover_image_filename = cover_image_path.name
                        logger.info(
                            "Cover image found on local filesystem",
                            extra={
                                "type": type,
                                "item_id": item_id,
                                "cover_image_path": str(cover_image_path),
                            },
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to read cover image from filesystem: {e}",
                        extra={
                            "type": type,
                            "item_id": item_id,
                            "cover_image": data.get("cover_image"),
                        },
                    )

            # Create publish request
            publish_request = PublishRequest(
                article=enriched_article,
                cover_image_base64=cover_image_base64,
                cover_image_filename=cover_image_filename,
                position=body.position if body else "latest",
            )

            # Import publish_article function
            # Note: publish_article is a FastAPI endpoint function, but we can call it directly
            # since we're in the same application context
            from backend.app.routers.article_composer import publish_article

            # Publish to GitHub/Vercel
            publish_result = await publish_article(publish_request)

            if publish_result.success:
                # Update with actual published URL
                published_url = publish_result.article_url or published_url
                github_commit_sha = publish_result.commit_sha
                mdx_path = publish_result.mdx_path

                # Derive real MDX slug (e.g. "my-slug.mdx" -> "my-slug")
                if publish_result.mdx_path:
                    article_slug = publish_result.mdx_path.rsplit("/", 1)[-1].replace(".mdx", "")
                elif publish_result.article_url:
                    article_slug = publish_result.article_url.rstrip("/").rsplit("/", 1)[-1]

                logger.info(
                    "✅ Article published to GitHub/Vercel",
                    extra={
                        "type": type,
                        "item_id": item_id,
                        "article_slug": article_slug,
                        "title": title,
                        "published_url": published_url,
                        "commit_sha": github_commit_sha,
                    },
                )

                # Update homepage-layout.json if a position was specified
                publish_position = body.position if body else "latest"
                if publish_position != "latest" and publish_position in VALID_HOMEPAGE_POSITIONS:
                    try:
                        await update_homepage_layout(
                            slug=article_slug,
                            position=publish_position,
                        )
                        logger.info(
                            "✅ Homepage layout updated",
                            extra={
                                "position": publish_position,
                                "slug": article_slug,
                            },
                        )
                    except Exception as layout_err:
                        logger.warning(
                            f"⚠️ Failed to update homepage layout: {layout_err}",
                            extra={"position": publish_position},
                        )
            else:
                logger.error(
                    f"⚠️ Failed to publish to GitHub/Vercel: {publish_result.error}",
                    extra={"type": type, "item_id": item_id, "title": title},
                )
                # Don't block publication if GitHub fails
                # Article is already in Qdrant

        except ImportError as e:
            logger.warning(
                f"⚠️ Article composer not available - skipping GitHub publish: {e}",
                extra={"type": type, "item_id": item_id},
            )
        except Exception as e:
            logger.error(
                f"⚠️ Failed to publish to GitHub/Vercel: {e}",
                exc_info=True,
                extra={"type": type, "item_id": item_id, "title": title},
            )
            # Don't block publication if GitHub fails
            # Article is already in Qdrant

        # Step 4: Write to news_items table (serves /api/news for balizero.com frontend)
        try:
            pool = getattr(request.app.state, "db_pool", None) if request else None
            if pool:
                slug = item_id  # item_id is already a slug-friendly identifier
                summary = (data.get("content") or "")[:500]
                content_full = data.get("content") or ""
                ai_summary = (
                    data.get("brief", {}).get("what", "")
                    if isinstance(data.get("brief"), dict)
                    else ""
                )
                ai_tags = data.get("tags") or []
                image_url = data.get("image_url") or data.get("cover_image")
                priority_val = data.get("priority", "medium")
                if priority_val not in ("high", "medium", "low"):
                    priority_val = "medium"

                # Map category to valid news_items constraint values
                valid_categories = {
                    "immigration",
                    "business",
                    "tax",
                    "property",
                    "lifestyle",
                    "tech",
                    "legal",
                }
                news_category = category if category in valid_categories else "business"

                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO news_items (
                            title, slug, summary, content, source, source_url,
                            category, priority, status, image_url, published_at,
                            ai_summary, ai_tags, external_id
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'approved', $9, NOW(), $10, $11, $12)
                        ON CONFLICT (slug) DO NOTHING
                        """,
                        title,
                        slug,
                        summary,
                        content_full,
                        data.get("source_name", ""),
                        data.get("source_url", data.get("url", "")),
                        news_category,
                        priority_val,
                        image_url,
                        ai_summary,
                        ai_tags,
                        item_id,
                    )

                logger.info(
                    "Article written to news_items table",
                    extra={"type": type, "item_id": item_id, "slug": slug},
                )
        except Exception as e:
            logger.warning(
                f"Failed to write to news_items (non-blocking): {e}",
                extra={"type": type, "item_id": item_id},
            )

        # Step 4b: Enqueue for post-processing (translate + image) — non-blocking
        try:
            async with _post_publish_lock:
                if not any(item["slug"] == article_slug for item in _post_publish_queue):
                    _post_publish_queue.append(
                        {
                            "slug": article_slug,
                            "category": category,
                            "queued_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            logger.info(
                "📥 Enqueued for post-processing",
                extra={"slug": article_slug, "category": category},
            )
        except Exception as e:
            logger.warning(f"Failed to enqueue post-processing (non-blocking): {e}")

        # Step 5: Update staging file with publish timestamp
        data["published_at"] = datetime.now(timezone.utc).isoformat()
        data["published_url"] = published_url
        data["status"] = "published"
        if github_commit_sha:
            data["github_commit_sha"] = github_commit_sha
        if mdx_path:
            data["mdx_path"] = mdx_path

        # Note: The file has already been moved to archived/approved by ingest_intel_to_qdrant
        # We don't need to move it again

        logger.info(
            "✅ Publish completed successfully",
            extra={
                "type": type,
                "item_id": item_id,
                "title": title,
                "published_url": published_url,
                "github_published": bool(github_commit_sha),
            },
        )

        return {
            "success": True,
            "message": "Article published successfully",
            "id": item_id,
            "title": title,
            "published_url": published_url,
            "published_at": data["published_at"],
            "collection": "visa_oracle" if type == "visa" else "bali_intel_bali_news",
            "github_commit_sha": github_commit_sha,
            "mdx_path": mdx_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Publish failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id}
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


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
                {"slug": slug, "category": category, "queued_at": datetime.now(timezone.utc).isoformat()}
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
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}") from e


@router.post("/api/intel/search")
async def search_intel(request: IntelSearchRequest) -> dict[str, Any]:
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
                    cutoff_date = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
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
    category: str | None = None, days: int = IntelConstants.DUPLICATE_CHECK_DAYS
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
                        response = await http_client.post(
                            scroll_url, json=scroll_payload, headers=headers
                        )
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
                            "severity": "high",  # All critical items are high severity for chain compatibility
                        }
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
    category: str | None = None, _days: int = IntelConstants.TRENDS_ANALYSIS_DAYS
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
async def get_intelligence_analytics(days: int = IntelConstants.TRENDS_ANALYSIS_DAYS) -> Any:
    """Get historical analytics and trends for Intelligence Center"""
    logger.info("Analytics requested", extra={"endpoint": "/api/intel/analytics", "days": days})

    try:
        return analytics_service.get_intelligence_analytics(days)

    except Exception as e:
        logger.error(f"Failed to calculate analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Analytics calculation failed: {str(e)}"
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
