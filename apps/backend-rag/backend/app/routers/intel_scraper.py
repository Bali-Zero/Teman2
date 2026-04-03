"""
Intel Scraper & Publish Endpoints

Split from intel.py for maintainability.
Provides: scraper submission, register notification, ingest to Qdrant,
publish staging items, homepage layout update, convert staging to article.
"""

import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path as PathLib
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.core.config import settings
from backend.app.metrics import (
    intel_articles_duplicates,
    intel_articles_submitted,
    intel_scraper_latency,
    intel_user_actions_total,
)
from backend.app.routers.intel import (
    INTEL_COLLECTIONS,
    VALID_HOMEPAGE_POSITIONS,
    PublishToSiteRequest,
    RegisterNotificationRequest,
    ScraperSubmission,
    classification_service,
    embedder,
    staging_service,
)
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.app.utils.logging_utils import get_logger
from backend.core.qdrant_db import QdrantClient

logger = get_logger(__name__)

router = APIRouter(tags=["intel-scraper"])

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
        r"## Summary\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE,
    )
    ai_summary = summary_match.group(1).strip() if summary_match else content[:280]

    # Extract Facts section
    facts_match = re.search(r"## Facts\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE)
    facts = facts_match.group(1).strip() if facts_match else content

    # Extract Bali Zero Take section
    bali_zero_take_match = re.search(
        r"## Bali Zero Take\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE,
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
        r"## Next Steps\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE,
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
            submission.category, submission.title, submission.content,
        )

        # Generate unique item ID
        item_id = staging_service.generate_item_id(
            intel_type, submission.title, submission.source_url,
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
                time.time() - start_time,
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
            scraper_type=submission.source_name, intel_type=intel_type, tier=submission.tier,
        ).inc()
        intel_scraper_latency.labels(scraper_type=submission.source_name).observe(
            time.time() - start_time,
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
                status_code=500, detail="Failed to ingest article to knowledge base",
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
                            "utf-8",
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

            # Priority 3: Generate on-demand via Fireworks.ai Flux.1 Dev
            # Triggered at approval time — only for articles without a pre-generated cover
            if not cover_image_base64:
                fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
                if fireworks_key:
                    try:
                        import urllib.error
                        import urllib.parse
                        import urllib.request

                        # Build editorial prompt (inline — no scraper dependency)
                        _headline = title
                        _category = category
                        _summary = data.get("content", "")[:500]
                        _prompt = (
                            f"Cinematic editorial photograph for a news article titled '{_headline}'. "
                            f"Category: {_category}. "
                            f"Scene: {_summary[:200] if _summary else 'Indonesian business and lifestyle in Bali'}. "
                            "Shot on ARRI Alexa Mini LF 35mm lens, teal and amber color grading, "
                            "golden hour light, hyper-realistic, film grain, no text, no watermarks, "
                            "purely visual scene."
                        )
                        _negative = (
                            "text, watermark, logo, signature, caption, illustration, cartoon, "
                            "anime, flat design, 3D render, CGI, neon colors, cyberpunk, "
                            "smiling businesspeople, handshake, stock photo, blurry, low quality"
                        )
                        _fw_url = (
                            "https://api.fireworks.ai/inference/v1/workflows/"
                            "accounts/fireworks/models/flux-1-dev-fp8/text_to_image"
                        )
                        _payload = json.dumps({
                            "prompt": _prompt,
                            "negative_prompt": _negative,
                            "width": 1344,
                            "height": 768,
                            "steps": 28,
                            "cfg_scale": 3.5,
                        }).encode()
                        _req = urllib.request.Request(
                            _fw_url,
                            data=_payload,
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {fireworks_key}",
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Accept": "*/*",
                                "Origin": "https://fireworks.ai",
                                "Referer": "https://fireworks.ai/",
                            },
                        )
                        _resp = await asyncio.to_thread(
                            urllib.request.urlopen, _req, None, 60,  # 60s timeout
                        )
                        _img_bytes = await asyncio.to_thread(_resp.read)
                        if len(_img_bytes) > 5000:
                            cover_image_base64 = base64.b64encode(_img_bytes).decode("utf-8")
                            cover_image_filename = f"{item_id}_cover.png"
                            logger.info(
                                "✅ Cover image generated via Fireworks.ai Flux.1 Dev",
                                extra={
                                    "type": type,
                                    "item_id": item_id,
                                    "size_bytes": len(_img_bytes),
                                },
                            )
                        else:
                            logger.warning(
                                "Fireworks image response too small — skipping",
                                extra={"type": type, "item_id": item_id},
                            )
                    except Exception as e:
                        logger.warning(
                            f"Cover image generation via Fireworks failed (non-blocking): {e}",
                            extra={"type": type, "item_id": item_id},
                        )
                else:
                    logger.info(
                        "FIREWORKS_API_KEY not set — publishing without cover image",
                        extra={"type": type, "item_id": item_id},
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

        # Step 4b: Enqueue for post-processing (translate + image + SEO) — DB-backed
        try:
            if not pool:
                pool = getattr(request.app.state, "db_pool", None) if request else None
            if not pool:
                raise RuntimeError("No DB pool available")
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO post_publish_queue (slug, category, source)
                    VALUES ($1, $2, 'intel')
                    ON CONFLICT (slug) DO NOTHING
                    """,
                    article_slug, category,
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
            f"Publish failed: {e}", exc_info=True, extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


