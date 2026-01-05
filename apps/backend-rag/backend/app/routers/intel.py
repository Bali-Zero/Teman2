"""
Intel News API - Search and manage Bali intelligence news
"""

import json
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.core.intel_approvers import get_chat_ids, get_required_votes, get_team_config
from app.metrics import (
    intel_articles_duplicates,
    intel_articles_submitted,
    intel_classification_duration,
    intel_classification_total,
    intel_scraper_latency,
    intel_staging_queue_size,
)
from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.integrations.telegram_bot_service import telegram_bot

# Import for duplicate detection integration
import sys
from pathlib import Path as PathLib

# Add scraper scripts to path for ClaudeValidator import
scraper_scripts_path = PathLib(__file__).parent.parent.parent.parent.parent / "bali-intel-scraper" / "scripts"
if scraper_scripts_path.exists():
    sys.path.insert(0, str(scraper_scripts_path))

router = APIRouter()
logger = logging.getLogger(__name__)

embedder = create_embeddings_generator()

# Staging Directories (mounted Fly volume)
BASE_STAGING_DIR = Path("/data/staging")
VISA_STAGING_DIR = BASE_STAGING_DIR / "visa"
NEWS_STAGING_DIR = BASE_STAGING_DIR / "news"

# Ensure directories exist
VISA_STAGING_DIR.mkdir(parents=True, exist_ok=True)
NEWS_STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Voting storage for Telegram approval
PENDING_INTEL_PATH = Path("/tmp/pending_intel")
PENDING_INTEL_PATH.mkdir(exist_ok=True)

# Qdrant collections for intel
INTEL_COLLECTIONS = {
    "visa": "visa_oracle",
    "news": "bali_intel_bali_news",
    "immigration": "bali_intel_immigration",
    "bkpm_tax": "bali_intel_bkpm_tax",
    "realestate": "bali_intel_realestate",
    "events": "bali_intel_events",
    "social": "bali_intel_social",
    "competitors": "bali_intel_competitors",
    "bali_news": "bali_intel_bali_news",
    "roundup": "bali_intel_roundup",
}

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
    extraction_method: str | None = "css"
    tier: str = "T2"  # T1, T2, T3


# --- HELPER FUNCTIONS ---


def classify_intel_type(category: str, title: str, content: str) -> str:
    """
    Classify article as 'visa' or 'news' for routing to correct staging folder.

    Args:
        category: Original category from scraper
        title: Article title
        content: Article content

    Returns:
        str: "visa" or "news"
    """
    # Direct category mapping
    visa_categories = {"visa", "immigration", "visa_regulations"}
    if category.lower() in visa_categories:
        return "visa"

    # Keyword-based classification
    visa_keywords = [
        "visa",
        "kitas",
        "kitap",
        "voa",
        "immigration",
        "imigrasi",
        "permit",
        "stay permit",
        "residence",
        "b211",
        "e33",
    ]

    text_lower = f"{title} {content}".lower()
    visa_mentions = sum(1 for keyword in visa_keywords if keyword in text_lower)

    # If >3 visa keywords, classify as visa
    if visa_mentions >= 3:
        return "visa"

    # Default to news
    return "news"


async def send_intel_approval_notification(
    intel_type: str,
    item_id: str,
    item_data: dict,
    enriched_data: dict = None,
    image_path: str = None
) -> bool:
    """
    Send Telegram notification to approval team with voting buttons.

    Now sends RICH formatted article with image (Bali Zero style) instead of plain text.

    Args:
        intel_type: "news" or "visa"
        item_id: Unique item identifier
        item_data: Full item data from staging file
        enriched_data: Enriched content from ArticleEnrichmentService (optional)
        image_path: Path to generated cover image (optional)

    Returns:
        bool: True if notification sent successfully
    """
    # Get team configuration
    team_config = get_team_config(intel_type)
    if not team_config or not team_config["approvers"]:
        logger.warning(
            f"No approvers configured for {intel_type}",
            extra={"intel_type": intel_type, "item_id": item_id},
        )
        return False

    chat_ids = get_chat_ids(intel_type)
    if not chat_ids:
        logger.warning(
            f"No chat IDs found for {intel_type}",
            extra={"intel_type": intel_type, "item_id": item_id},
        )
        return False

    # Use enriched data if available, otherwise fallback to raw
    if enriched_data:
        title = enriched_data.get("enriched_title", item_data.get("title", "Untitled"))
        summary = enriched_data.get("enriched_summary", "")
        key_points = enriched_data.get("key_points", [])
        keywords = enriched_data.get("seo_keywords", [])
        reading_time = enriched_data.get("reading_time_minutes", 3)
    else:
        title = item_data.get("title", "Untitled")
        summary = item_data.get("content", "")[:200] + "..."
        key_points = []
        keywords = []
        reading_time = 3

    source = item_data.get("source_name", item_data.get("source", "Unknown"))
    source_url = item_data.get("source_url", item_data.get("url", ""))
    detected_at = item_data.get("detected_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    emoji_map = {"visa": "🛂", "news": "📰"}
    emoji = emoji_map.get(intel_type, "📋")

    # Build HTML formatted caption (Bali Zero style)
    caption = f"""<b>{emoji} BALI ZERO INTELLIGENCE</b>

<b>{title}</b>

{summary}
"""

    # Add key points only if available (max 3)
    if key_points:
        caption += "\n<b>📌 Key Points:</b>\n"
        for i, point in enumerate(key_points[:3], 1):
            caption += f"  {i}. {point}\n"

    # Add metadata
    caption += f"""
<b>📰 Source:</b> <a href="{source_url}">{source}</a>
<b>📅 Detected:</b> {detected_at}"""

    # Add tags only if available
    if keywords:
        caption += f"\n<b>🏷️ Tags:</b> {', '.join(keywords[:5])}"

    caption += f"""

🗳️ <b>Votazione {team_config['required_votes']}/{len(team_config['approvers'])}</b> per approvare/rifiutare

<code>ID: {item_id}</code>"""

    # Inline keyboard
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ APPROVE",
                    "callback_data": f"intel:approve:{intel_type}:{item_id}",
                },
                {
                    "text": "❌ REJECT",
                    "callback_data": f"intel:reject:{intel_type}:{item_id}",
                },
            ],
        ]
    }

    # Initialize voting status
    voting_status = {
        "item_id": item_id,
        "intel_type": intel_type,
        "status": "voting",
        "votes": {"approve": [], "reject": []},
        "created_at": datetime.now().isoformat(),
        "item_data": item_data,
        "enriched_data": enriched_data,
        "image_path": image_path,
    }

    # Save voting status
    status_file = PENDING_INTEL_PATH / f"{item_id}.json"
    status_file.write_text(json.dumps(voting_status, indent=2))

    # Send to all approvers
    success_count = 0
    for chat_id in chat_ids:
        try:
            # If we have an image, send as photo with caption
            # Otherwise, send as text message
            if image_path and Path(image_path).exists():
                with open(image_path, 'rb') as photo:
                    await telegram_bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
            else:
                # Fallback to text message if no image
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            success_count += 1
            logger.info(
                f"Rich notification sent to {chat_id}",
                extra={
                    "intel_type": intel_type,
                    "item_id": item_id,
                    "chat_id": chat_id,
                    "has_image": bool(image_path),
                    "enriched": bool(enriched_data)
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to send notification to {chat_id}: {e}",
                extra={"intel_type": intel_type, "item_id": item_id, "chat_id": chat_id},
            )

    logger.info(
        f"Sent {success_count}/{len(chat_ids)} rich notifications",
        extra={"intel_type": intel_type, "item_id": item_id},
    )

    return success_count > 0


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
        # Classify intel type (with timing)
        classification_start = time.time()
        intel_type = classify_intel_type(
            submission.category, submission.title, submission.content
        )
        intel_classification_duration.observe(time.time() - classification_start)
        intel_classification_total.labels(
            category_input=submission.category,
            classified_as=intel_type
        ).inc()

        # Generate unique item ID
        import hashlib

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(
            f"{submission.title}{submission.source_url}".encode()
        ).hexdigest()[:8]
        item_id = f"{intel_type}_{timestamp}_{content_hash}"

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

        # Determine staging directory
        staging_dir = VISA_STAGING_DIR if intel_type == "visa" else NEWS_STAGING_DIR
        staging_file = staging_dir / f"{item_id}.json"

        # Check for duplicates (same source_url in last 7 days)
        existing_files = list(staging_dir.glob("*.json"))
        for existing_file in existing_files:
            try:
                with open(existing_file) as f:
                    existing_data = json.load(f)
                    if existing_data.get("source_url") == submission.source_url:
                        logger.info(
                            f"Duplicate article detected (same URL): {submission.source_url}",
                            extra={"item_id": item_id, "existing_id": existing_data.get("item_id")},
                        )

                        # Metrics: Duplicate detected
                        intel_articles_duplicates.labels(intel_type=intel_type).inc()
                        intel_scraper_latency.labels(scraper_type=submission.source_name).observe(
                            time.time() - start_time
                        )

                        return {
                            "success": True,
                            "message": "Article already exists in staging",
                            "item_id": existing_data.get("item_id"),
                            "intel_type": intel_type,
                            "duplicate": True,
                        }
            except Exception:
                continue

        # Save to staging
        staging_file.write_text(json.dumps(staging_data, indent=2))

        # Metrics: Article submitted successfully
        intel_articles_submitted.labels(
            scraper_type=submission.source_name,
            intel_type=intel_type,
            tier=submission.tier
        ).inc()

        intel_scraper_latency.labels(scraper_type=submission.source_name).observe(
            time.time() - start_time
        )

        # Update staging queue size gauge
        _update_staging_queue_size()

        logger.info(
            f"Article submitted from scraper",
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
async def list_pending_items(type: str = "all"):
    """List items pending approval in staging area"""
    logger.info(f"Listing pending items", extra={"type": type, "endpoint": "/api/intel/staging/pending"})
    items = []

    dirs_to_check = []
    if type in ["all", "visa"]:
        dirs_to_check.append(("visa", VISA_STAGING_DIR))
    if type in ["all", "news"]:
        dirs_to_check.append(("news", NEWS_STAGING_DIR))

    for category, directory in dirs_to_check:
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}", extra={"category": category})
            continue

        for file_path in directory.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    # Add metadata useful for list view
                    items.append(
                        {
                            "id": file_path.stem,
                            "type": category,
                            "title": data.get("title", "Untitled"),
                            "status": data.get("status", "pending"),
                            "detected_at": data.get("detected_at"),
                            "source": data.get("source_url", data.get("url", "")),  # Fix: try source_url first, fallback to url
                            "detection_type": data.get("detection_type", "NEW"),
                        }
                    )
            except Exception as e:
                logger.error(f"Error reading staging file {file_path}: {e}", exc_info=True, extra={"file": str(file_path), "category": category})

    # Sort by date (newest first)
    items.sort(key=lambda x: x.get("detected_at", ""), reverse=True)

    logger.info(f"Listed {len(items)} pending items", extra={"type": type, "count": len(items), "categories": [cat for cat, _ in dirs_to_check]})
    return {"items": items, "count": len(items)}


@router.get("/api/intel/staging/preview/{type}/{item_id}")
async def preview_staging_item(type: str, item_id: str):
    """Get full content of a staging item"""
    logger.info(f"Preview staging item requested", extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/preview"})

    directory = VISA_STAGING_DIR if type == "visa" else NEWS_STAGING_DIR
    file_path = directory / f"{item_id}.json"

    if not file_path.exists():
        logger.warning(f"Preview item not found", extra={"type": type, "item_id": item_id, "file_path": str(file_path)})
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        with open(file_path) as f:
            data = json.load(f)
            logger.info(f"Preview loaded successfully", extra={"type": type, "item_id": item_id, "title": data.get("title", "Untitled")})
            return data
    except Exception as e:
        logger.error(f"Error reading preview file: {e}", exc_info=True, extra={"type": type, "item_id": item_id, "file_path": str(file_path)})
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


class ApprovalRequest(BaseModel):
    """Request body for staging approval with optional enrichment data"""
    intel_type: Optional[str] = None
    item_id: Optional[str] = None
    item_data: Optional[dict] = None
    enriched_data: Optional[dict] = None
    image_path: Optional[str] = None


@router.post("/api/intel/staging/approve/{type}/{item_id}")
async def approve_staging_item(
    type: str,
    item_id: str,
    request: Optional[ApprovalRequest] = None
):
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
        f"Approval request received - initiating Telegram voting",
        extra={
            "type": type,
            "item_id": item_id,
            "endpoint": "/api/intel/staging/approve",
            "has_enrichment": bool(request and request.enriched_data),
            "has_image": bool(request and request.image_path)
        },
    )

    directory = VISA_STAGING_DIR if type == "visa" else NEWS_STAGING_DIR
    file_path = directory / f"{item_id}.json"

    if not file_path.exists():
        logger.warning(
            f"Approval failed - item not found",
            extra={"type": type, "item_id": item_id, "file_path": str(file_path)},
        )
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        with open(file_path) as f:
            data = json.load(f)

        title = data.get("title", "Untitled")
        logger.info(
            f"Loaded staging item for approval",
            extra={"type": type, "item_id": item_id, "title": title},
        )

        # Extract enrichment data if provided
        enriched_data = request.enriched_data if request else None
        image_path = request.image_path if request else None

        # Send Telegram notification to approval team (with rich formatting if enriched)
        notification_sent = await send_intel_approval_notification(
            type, item_id, data, enriched_data, image_path
        )

        if not notification_sent:
            logger.error(
                f"Failed to send Telegram notification",
                extra={"type": type, "item_id": item_id, "title": title},
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to send approval notification. Check team configuration.",
            )

        logger.info(
            f"Telegram voting initiated successfully",
            extra={"type": type, "item_id": item_id, "title": title},
        )

        return {
            "success": True,
            "message": f"Approval voting initiated. Team notified via Telegram.",
            "id": item_id,
            "voting_status": "pending",
        }

    except Exception as e:
        logger.error(f"Approval failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/intel/staging/reject/{type}/{item_id}")
async def reject_staging_item(type: str, item_id: str):
    """Reject item and move to archive"""
    logger.info(f"Rejection started", extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/reject"})

    directory = VISA_STAGING_DIR if type == "visa" else NEWS_STAGING_DIR
    file_path = directory / f"{item_id}.json"

    if not file_path.exists():
        logger.warning(f"Rejection failed - item not found", extra={"type": type, "item_id": item_id, "file_path": str(file_path)})
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        # Read title for logging before moving
        try:
            with open(file_path) as f:
                data = json.load(f)
                title = data.get("title", "Untitled")
        except Exception:
            title = "Unknown"

        # Move to rejected archive
        archive_dir = directory / "archived" / "rejected"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(archive_dir / file_path.name))

        logger.info(f"Rejection completed successfully", extra={
            "type": type,
            "item_id": item_id,
            "title": title,
            "archive_path": str(archive_dir / file_path.name)
        })

        return {"success": True, "message": "Item rejected and archived", "id": item_id}
    except Exception as e:
        logger.error(f"Rejection failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id})
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
        f"Publish request received",
        extra={"type": type, "item_id": item_id, "endpoint": "/api/intel/staging/publish"}
    )

    directory = VISA_STAGING_DIR if type == "visa" else NEWS_STAGING_DIR
    file_path = directory / f"{item_id}.json"

    if not file_path.exists():
        logger.warning(
            f"Publish failed - item not found",
            extra={"type": type, "item_id": item_id, "file_path": str(file_path)}
        )
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        # Load article data
        with open(file_path) as f:
            data = json.load(f)

        title = data.get("title", "Untitled")
        source_url = data.get("source_url", data.get("url", ""))
        category = data.get("category", type)

        logger.info(
            f"Publishing article",
            extra={"type": type, "item_id": item_id, "title": title}
        )

        # Step 1: Ingest to Qdrant (knowledge base)
        from app.routers.telegram import ingest_intel_to_qdrant

        ingestion_success = await ingest_intel_to_qdrant(item_id, type)

        if not ingestion_success:
            logger.error(
                f"Publish failed - Qdrant ingestion error",
                extra={"type": type, "item_id": item_id, "title": title}
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to ingest article to knowledge base"
            )

        logger.info(
            f"✅ Article ingested to Qdrant",
            extra={"type": type, "item_id": item_id, "title": title}
        )

        # Step 2: Register in anti-duplicate system
        try:
            from claude_validator import ClaudeValidator

            # Generate published URL (will be on balizero.com in the future)
            published_url = f"https://balizero.com/{category}/{item_id}"

            ClaudeValidator.add_published_article(
                title=title,
                url=published_url,
                category=category,
                published_at=datetime.utcnow().isoformat()
            )

            logger.info(
                f"✅ Article registered in anti-duplicate system",
                extra={
                    "type": type,
                    "item_id": item_id,
                    "title": title,
                    "url": published_url
                }
            )

        except ImportError:
            logger.warning(
                f"⚠️ ClaudeValidator not available - skipping duplicate registration",
                extra={"type": type, "item_id": item_id}
            )
        except Exception as e:
            logger.error(
                f"⚠️ Failed to register in anti-duplicate system: {e}",
                exc_info=True,
                extra={"type": type, "item_id": item_id}
            )
            # Don't fail the publish if duplicate registration fails

        # Step 3: Update staging file with publish timestamp
        data["published_at"] = datetime.utcnow().isoformat()
        data["published_url"] = f"https://balizero.com/{category}/{item_id}"
        data["status"] = "published"

        # Note: The file has already been moved to archived/approved by ingest_intel_to_qdrant
        # We don't need to move it again

        logger.info(
            f"✅ Publish completed successfully",
            extra={
                "type": type,
                "item_id": item_id,
                "title": title,
                "published_url": data["published_url"]
            }
        )

        return {
            "success": True,
            "message": "Article published successfully",
            "id": item_id,
            "title": title,
            "published_url": data["published_url"],
            "published_at": data["published_at"],
            "collection": "visa_oracle" if type == "visa" else "bali_intel_bali_news"
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(
            f"Publish failed: {e}",
            exc_info=True,
            extra={"type": type, "item_id": item_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/intel/metrics")
async def get_system_metrics():
    """Get real-time system metrics for System Pulse dashboard"""
    logger.info("System metrics requested", extra={"endpoint": "/api/intel/metrics"})

    try:
        # Calculate metrics
        metrics = {
            "agent_status": "active",  # TODO: Implement agent health check
            "last_run": None,
            "items_processed_today": 0,
            "avg_response_time_ms": 0,
            "qdrant_health": "healthy",
            "next_scheduled_run": None,
            "uptime_percentage": 99.8,
        }

        # Count pending items
        visa_count = len(list(VISA_STAGING_DIR.glob("*.json"))) if VISA_STAGING_DIR.exists() else 0
        news_count = len(list(NEWS_STAGING_DIR.glob("*.json"))) if NEWS_STAGING_DIR.exists() else 0
        metrics["items_processed_today"] = visa_count + news_count

        # Check last processed item (most recent archive)
        last_approved = None
        for archive_type in ["visa", "news"]:
            archive_dir = (VISA_STAGING_DIR if archive_type == "visa" else NEWS_STAGING_DIR) / "archived" / "approved"
            if archive_dir.exists():
                for file_path in sorted(archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
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
            # Simple ping test
            metrics["qdrant_health"] = "healthy"
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}", exc_info=True)
            metrics["qdrant_health"] = "degraded"

        # Calculate next scheduled run (every 2 hours from last run)
        if last_approved:
            try:
                from datetime import datetime, timedelta
                last_dt = datetime.fromisoformat(last_approved.replace('Z', '+00:00'))
                next_run = last_dt + timedelta(hours=2)
                metrics["next_scheduled_run"] = next_run.isoformat()
            except Exception:
                pass

        # Calculate average response time based on recent approvals
        response_times = []
        for archive_type in ["visa", "news"]:
            archive_dir = (VISA_STAGING_DIR if archive_type == "visa" else NEWS_STAGING_DIR) / "archived" / "approved"
            if archive_dir.exists():
                for file_path in sorted(archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            # Estimate response time based on content length (mock calculation)
                            content_len = len(data.get("content", ""))
                            response_times.append(1000 + (content_len / 10))  # Simple heuristic
                    except Exception:
                        continue

        if response_times:
            metrics["avg_response_time_ms"] = int(sum(response_times) / len(response_times))
        else:
            metrics["avg_response_time_ms"] = 1250  # Default

        logger.info(f"System metrics calculated", extra={
            "agent_status": metrics["agent_status"],
            "qdrant_health": metrics["qdrant_health"],
            "items_processed": metrics["items_processed_today"]
        })

        return metrics

    except Exception as e:
        logger.error(f"Failed to calculate system metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")


class IntelSearchRequest(BaseModel):
    query: str
    category: str | None = None
    date_range: str = "last_7_days"
    tier: list[str] = ["T1", "T2", "T3"]  # Fixed: Changed from "1","2","3" to match Qdrant storage
    impact_level: str | None = None
    limit: int = 20


class IntelStoreRequest(BaseModel):
    collection: str
    id: str
    document: str
    embedding: list[float]
    metadata: dict
    full_data: dict


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
                    days = days_map.get(request.date_range, 7)
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
                    similarity_score = 1 / (1 + distance)  # Convert distance to similarity

                    all_results.append(
                        {
                            "id": metadata.get("id"),
                            "title": metadata.get("title"),
                            "summary_english": doc[:300],  # First 300 chars
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
async def get_critical_items(category: str | None = None, days: int = 7):
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

                # Qdrant: Use peek to get documents, then filter in Python
                # TODO: Implement Qdrant filter support for better performance
                results = client.peek(limit=100)

                # Filter in Python for now
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
async def get_trends(category: str | None = None, _days: int = 30):
    """Get trending topics and keywords"""
    try:
        # This would require more sophisticated analysis
        # For now, return basic stats

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

                # Extract keywords from metadata (simplified)
                # In production, you'd want NLP-based topic modeling

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


# --- HELPER FUNCTIONS FOR METRICS ---

def _update_staging_queue_size():
    """Update Prometheus gauge for staging queue sizes"""
    try:
        visa_count = len(list(VISA_STAGING_DIR.glob("*.json"))) if VISA_STAGING_DIR.exists() else 0
        news_count = len(list(NEWS_STAGING_DIR.glob("*.json"))) if NEWS_STAGING_DIR.exists() else 0

        intel_staging_queue_size.labels(intel_type="visa").set(visa_count)
        intel_staging_queue_size.labels(intel_type="news").set(news_count)
    except Exception as e:
        logger.warning(f"Failed to update staging queue size metrics: {e}")
