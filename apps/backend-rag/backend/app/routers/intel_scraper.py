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

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user
from backend.app.metrics import (
    intel_articles_duplicates,
    intel_articles_submitted,
    intel_scraper_latency,
    intel_user_actions_total,
)
from backend.app.routers.intel import (
    INTEL_COLLECTIONS,
    PublishToSiteRequest,
    RegisterNotificationRequest,
    ScraperSubmission,
    classification_service,
    get_embedder,
    staging_service,
)
from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.app.utils.logging_utils import get_logger
from backend.core.cache import invalidate_cache
from backend.core.qdrant_db import QdrantClient
from backend.services.article_routes import served_category
from backend.services.cover_images import _cover_as_jpeg
from backend.services.intel.intel_staging_service import assert_valid_item_id

logger = get_logger(__name__)

router = APIRouter(tags=["intel-scraper"])


def _require_publish_admin(user: dict[str, Any]) -> None:
    """Gate publish-to-public-website to admins. Raises 403 otherwise.

    Publishing opens a PR against the public site repo, so an authenticated
    team member is not a sufficient principal (Case OS R3).
    """
    if not is_crm_admin(user):
        raise HTTPException(status_code=403, detail="Publish requires admin")


# --- CONVERSION FUNCTIONS ---


def _summary_from_content(content: str, limit: int = 300) -> str:
    """Extract a complete-sentence summary from the first prose paragraph."""
    paragraph_lines: list[str] = []
    for line in content.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            if paragraph_lines:
                break
            continue
        if re.match(r"^#{1,6}\s", stripped_line):
            continue
        paragraph_lines.append(stripped_line)

    paragraph = " ".join(paragraph_lines)
    paragraph = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", paragraph)
    paragraph = re.sub(r"[*_`]", "", paragraph).strip()
    if not paragraph:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    summary_sentences: list[str] = []
    summary_length = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        separator_length = 1 if summary_sentences else 0
        if summary_length + separator_length + len(sentence) > limit:
            break
        summary_sentences.append(sentence)
        summary_length += separator_length + len(sentence)

    if summary_sentences:
        return " ".join(summary_sentences).rstrip(" (—-,;:")

    words = paragraph.split()
    truncated_words: list[str] = []
    for word in words:
        candidate = " ".join([*truncated_words, word])
        if len(candidate) + 1 > limit:
            break
        truncated_words.append(word)

    return " ".join(truncated_words).rstrip(" (—-,;:") + "…"


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
        r"## Summary\s*\n(.*?)(?=\n## |$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    ai_summary = (
        summary_match.group(1).strip()[:280] if summary_match else _summary_from_content(content)
    )

    # Extract Facts section
    facts_match = re.search(r"## Facts\s*\n(.*?)(?=\n## |$)", content, re.DOTALL | re.IGNORECASE)
    facts = facts_match.group(1).strip() if facts_match else content

    # Extract Bali Zero Take section
    bali_zero_take_match = re.search(
        r"## Bali Zero Take\s*\n(.*?)(?=\n## |$)",
        content,
        re.DOTALL | re.IGNORECASE,
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
        r"## Next Steps\s*\n(.*?)(?=\n## |$)",
        content,
        re.DOTALL | re.IGNORECASE,
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
        "ai_summary": ai_summary,
        "ai_tags": ai_tags[:5],  # Limit to 5 tags
        "suggested_components": suggested_components[:3],  # Limit to 3 components
        "cover_image": None,  # Will be set from staging_data if available
        "source": source_name,
        "source_url": source_url,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "seo_title": staging_data.get("seo_title"),
        "seo_description": staging_data.get("seo_description"),
        "cover_image_alt": staging_data.get("cover_image_alt"),
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
    await invalidate_cache("zantara:intel_scraper:*")
    return {
        "success": True,
        "message_id": request.telegram_message_id,
        "item_id": request.item_id,
    }


def _derive_tier_from_score(score: Any) -> str:
    """Bucket a live_news_score into the enricher's tier scheme.

    WR2 liveness rewire — red-team round FIX3, 2026-07-18. Mirrors
    claude_cli_enricher._normalize_live_news_fields's own buckets
    (>=80 breaking, >=40 developing, else evergreen) so a submission that
    carries a score WITHOUT an explicit tier doesn't silently default to
    "evergreen" and fall out of wr2_topic_selector's live pool (a score=85
    item with no tier previously persisted as 85/"evergreen" — excluded).
    Defensive against non-numeric input even though ScraperSubmission
    already validates `live_news_score` as `int | None`.
    """
    try:
        s = int(round(float(score)))
    except (TypeError, ValueError):
        return "evergreen"
    if s >= 80:
        return "breaking"
    if s >= 40:
        return "developing"
    return "evergreen"


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
            submission.category,
            submission.title,
            submission.content,
        )

        # Generate unique item ID
        item_id = staging_service.generate_item_id(
            intel_type,
            submission.title,
            submission.source_url,
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

            # Round-2 red-team MUST-FIX #3 (scar family #9): the early
            # return above happens BEFORE staging_data (with enrichment) is
            # built below, so a duplicate hit against an item written by an
            # older/partial-deploy scraper — enrichment absent or `{}` —
            # would leave that item's future draft stuck at `{}` forever
            # (7-day dedup window). Heal it in place: merge the new
            # submission's enrichment into the existing staging file when
            # the existing item doesn't already have a usable one. Never
            # let a heal failure turn a successful dedup into a 500 —
            # log and fall through to the unchanged response shape.
            enrichment_backfilled = False
            new_enrichment = submission.enrichment
            existing_enrichment = duplicate.get("enrichment")
            dup_item_id = duplicate.get("item_id")
            if (
                isinstance(new_enrichment, dict)
                and new_enrichment
                and not (isinstance(existing_enrichment, dict) and existing_enrichment)
                and dup_item_id
                and duplicate.get("status") in (None, "pending")
            ):
                try:
                    existing_full = staging_service.load_staging_item(intel_type, dup_item_id)
                    if existing_full is not None:
                        existing_full["enrichment"] = new_enrichment
                        staging_service.save_staging_item(intel_type, dup_item_id, existing_full)
                        enrichment_backfilled = True
                        logger.info(
                            "Backfilled enrichment onto duplicate staging item",
                            extra={"item_id": dup_item_id},
                        )
                except Exception:
                    logger.warning(
                        "Enrichment backfill failed for duplicate staging item "
                        "— dedup response unaffected",
                        extra={"item_id": dup_item_id},
                        exc_info=True,
                    )

            response: dict[str, Any] = {
                "success": True,
                "message": "Article already exists in staging",
                "item_id": duplicate.get("item_id"),
                "intel_type": intel_type,
                "duplicate": True,
            }
            if enrichment_backfilled:
                response["enrichment_backfilled"] = True
            return response

        # WR2 liveness rewire (SPRINT B1, scar family #9 break #2; red-team
        # FIX3 2026-07-18): normalize with uniform defaults so every staging
        # item — scraper sent them or not — has a consistent liveness shape
        # downstream. When liveness_tier is absent but a score IS present,
        # derive the tier from the score instead of defaulting to
        # "evergreen" — a validated, explicitly-provided tier is always
        # trusted as-is.
        _live_news_score = (
            submission.live_news_score if submission.live_news_score is not None else 0
        )
        _liveness_tier = (
            submission.liveness_tier
            if submission.liveness_tier is not None
            else _derive_tier_from_score(_live_news_score)
        )

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
            "live_news_score": _live_news_score,
            "liveness_tier": _liveness_tier,
            "live_news_reasons": [r.strip()[:200] for r in (submission.live_news_reasons or [])][
                :3
            ],
            # WR2 enrichment passthrough (scar family #9): carry the full
            # structured enricher object into staging so it survives to
            # wr2_topic_selector via list_pending_items' projection. Default
            # {} preserves today's behavior for legacy/partial-deploy
            # scrapers that don't send it yet.
            "enrichment": submission.enrichment or {},
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
                    "Failed to upload cover image to Drive: %s",
                    e,
                    extra={"item_id": item_id},
                )

        # Save to staging using service
        staging_file = staging_service.save_staging_item(intel_type, item_id, staging_data)

        # Metrics
        intel_articles_submitted.labels(
            scraper_type=submission.source_name,
            intel_type=intel_type,
            tier=submission.tier,
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

        await invalidate_cache("zantara:intel_scraper:*")
        return {
            "success": True,
            "message": f"Article saved to {intel_type} staging",
            "item_id": item_id,
            "intel_type": intel_type,
            "staging_path": str(staging_file),
            "duplicate": False,
        }

    except Exception as e:
        logger.exception("Failed to submit article from scraper: %s", e)
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
                "No Qdrant collection mapped for intel_type=%s",
                intel_type,
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
        embedding = await get_embedder().generate_single_embedding(embed_text)

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
            "Qdrant ingestion failed: %s",
            e,
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
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Publish approved item to Qdrant knowledge base and register in anti-duplicate system.

    News Room requests must carry an explicit body such as
    ``{"position": "hero_main"}``; there is no editorial placement default.

    This endpoint:
    1. Ingests article to Qdrant (knowledge base)
    2. Registers article in anti-duplicate system
    3. Archives to published folder

    Admin-only: publishing pushes the article to the PUBLIC website
    (balizero.com) via a GitHub PR, so it is an R3 (world-visible) action.
    Being an authenticated team member is not enough.

    Internal callers that carry their own authorization (e.g. the Telegram
    approval quorum) must call :func:`publish_staging_item_internal` instead,
    which names the actor explicitly rather than bypassing the gate.
    """
    _require_publish_admin(current_user)
    if type == "news" and body is None:
        raise HTTPException(
            status_code=422,
            detail="News Room publication requires an explicit homepage position",
        )
    return await _publish_staging_item(
        type=type,
        item_id=item_id,
        body=body,
        request=request,
        actor=(current_user.get("email") or "unknown"),
        allow_generated_cover=True,
    )


async def publish_staging_item_internal(
    intel_type: str,
    item_id: str,
    actor: str,
    allow_generated_cover: bool = True,
    position: str = "latest",
    *,
    pool: Any | None = None,
) -> dict[str, Any]:
    """Publish path for internal callers that carry their own authorization.

    ``actor`` names the authority that approved the publish (e.g.
    ``"telegram:quorum"``) and is written to the audit log. It is NOT a
    bypass hatch: only add a caller here when the caller itself gates the
    action, and say so at the call site.
    """
    return await _publish_staging_item(
        type=intel_type,
        item_id=item_id,
        body=PublishToSiteRequest(position=position),
        request=None,
        actor=actor,
        allow_generated_cover=allow_generated_cover,
        pool=pool,
    )


def _resolve_publish_pool(pool: Any | None, request: Request | None) -> Any | None:
    """Prefer an explicitly supplied pool for internal publish callers."""
    if pool is not None:
        return pool
    return getattr(request.app.state, "db_pool", None) if request else None


async def _publish_staging_item(
    type: str,
    item_id: str,
    body: PublishToSiteRequest | None,
    request: Request | None,
    actor: str,
    allow_generated_cover: bool = True,
    *,
    pool: Any | None = None,
) -> dict[str, Any]:
    """Publish implementation. Callers are responsible for authorization."""
    # Single funnel-in for both callers (the admin HTTP endpoint and the Telegram
    # quorum), so the id is judged once for the whole publish path.
    #
    # Honest statement of what this changes: the `staging_dir / f"{item_id}.json"`
    # write ~450 lines below is NOT reachable today with a malformed id, because
    # `load_staging_item` (7 lines down) rejects one by returning None and this
    # function 404s. That defense is real but REMOTE — it lives in another module and
    # is a side effect of a read's not-found contract, not a statement about the
    # write. This makes the invariant local and explicit; it is what a refactor of
    # that contract would otherwise silently remove.
    try:
        assert_valid_item_id(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "Publish request received",
        extra={
            "type": type,
            "item_id": item_id,
            "endpoint": "/api/intel/staging/publish",
            "actor": actor,
        },
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
                status_code=500,
                detail="Failed to ingest article to knowledge base",
            )

        logger.info(
            "✅ Article ingested to Qdrant",
            extra={"type": type, "item_id": item_id, "title": title},
        )

        # Step 2: Register in anti-duplicate system
        try:
            from claude_validator import ClaudeValidator

            published_url = f"{settings.balizero_website_url}/{served_category(category)}/{item_id}"

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
                "⚠️ Failed to register in anti-duplicate system: %s",
                e,
                exc_info=True,
                extra={"type": type, "item_id": item_id},
            )

        # Step 3: Publish to GitHub/Vercel → balizero.com
        published_url = f"{settings.balizero_website_url}/{served_category(category)}/{item_id}"
        github_commit_sha = None
        mdx_path = None
        article_slug = item_id  # fallback: use item_id if GitHub publish fails
        publish_result = None
        github_error: str | None = None

        try:
            from backend.app.routers.article_composer import (
                BaliZeroTake,
                EnrichedArticle,
                NextSteps,
                PublishRequest,
                TLDRSection,
                generate_slug,
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
                seo_title=enriched_dict.get("seo_title"),
                seo_description=enriched_dict.get("seo_description"),
                cover_image_alt=enriched_dict.get("cover_image_alt"),
            )

            # Prepare cover image if available
            cover_image_base64 = None
            cover_image_filename = None
            cover_slug = (data.get("slug") or "").strip() or generate_slug(title)

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
                        cover_image_base64 = base64.b64encode(_cover_as_jpeg(image_bytes)).decode(
                            "utf-8"
                        )
                        cover_image_filename = f"{cover_slug}.jpg"
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
                        "Failed to download cover image from Drive: %s",
                        e,
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
                        image_bytes = cover_image_path.read_bytes()
                        cover_image_base64 = base64.b64encode(_cover_as_jpeg(image_bytes)).decode("utf-8")
                        cover_image_filename = f"{cover_slug}.jpg"
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
                        "Failed to read cover image from filesystem: %s",
                        e,
                        extra={
                            "type": type,
                            "item_id": item_id,
                            "cover_image": data.get("cover_image"),
                        },
                    )

            # Priority 3: Generate on-demand via Fireworks.ai Flux.1 Dev.
            # The Damar workspace route disables this fallback so its static images
            # remain native-ImageGen assets prepared before publication.
            if not cover_image_base64 and not allow_generated_cover:
                raise HTTPException(
                    status_code=409,
                    detail="A readable pre-generated cover image is required",
                )
            if not cover_image_base64 and allow_generated_cover:
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
                        _payload = json.dumps(
                            {
                                "prompt": _prompt,
                                "negative_prompt": _negative,
                                "width": 1344,
                                "height": 768,
                                "steps": 28,
                                "cfg_scale": 3.5,
                            }
                        ).encode()
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
                            urllib.request.urlopen,
                            _req,
                            None,
                            60,  # 60s timeout
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
                            "Cover image generation via Fireworks failed (non-blocking): %s",
                            e,
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
                slug=data.get("slug"),
                publication_key=item_id,
            )

            # This path is already admin-gated at the endpoint above, so it calls
            # the implementation directly rather than the gated HTTP endpoint
            # (whose Depends() would not resolve on a direct Python call).
            from backend.app.routers.article_composer import publish_article_internal

            # Publish to GitHub/Vercel
            publish_result = await publish_article_internal(publish_request)

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

            else:
                github_error = publish_result.error or publish_result.message
                logger.error(
                    f"⚠️ Failed to publish to GitHub/Vercel: {publish_result.error}",
                    extra={"type": type, "item_id": item_id, "title": title},
                )
                # Don't block publication if GitHub fails
                # Article is already in Qdrant

        except HTTPException:
            raise
        except ImportError as e:
            logger.warning(
                "⚠️ Article composer not available - skipping GitHub publish: %s",
                e,
                extra={"type": type, "item_id": item_id},
            )
        except Exception as e:
            # NOTE: `type` is the route parameter (str) in this function scope,
            # not the builtin — use e.__class__.__name__ instead of type(e).
            github_error = f"{e.__class__.__name__}: {e}"
            logger.error(
                "⚠️ Failed to publish to GitHub/Vercel: %s",
                e,
                exc_info=True,
                extra={"type": type, "item_id": item_id, "title": title},
            )
            # Don't block publication if GitHub fails
            # Article is already in Qdrant

        # Step 4: Write to news_items table (serves /api/news for balizero.com frontend)
        try:
            publish_pool = _resolve_publish_pool(pool, request)
            if publish_pool:
                slug = article_slug or item_id
                summary = (data.get("content") or "")[:500]
                content_full = data.get("content") or ""
                ai_summary = (
                    data.get("brief", {}).get("what", "")
                    if isinstance(data.get("brief"), dict)
                    else ""
                )
                ai_tags = data.get("tags") or []
                if (
                    (
                        publish_result is not None
                        and publish_result.success
                        and publish_result.image_path
                    )
                    or data.get("published_cover_path")
                ):
                    image_url = f"/static/news/{slug}.jpg"
                else:
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

                # news_items.slug has no unique constraint on prod (only a plain
                # index), so ON CONFLICT (slug) raises; guard by existence instead.
                async with publish_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO news_items (
                            title, slug, summary, content, source, source_url,
                            category, priority, status, image_url, published_at,
                            ai_summary, ai_tags, external_id
                        )
                        SELECT $1, $2, $3, $4, $5, $6, $7, $8, 'approved', $9, NOW(), $10, $11, $12
                        WHERE NOT EXISTS (SELECT 1 FROM news_items WHERE slug = $2)
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
                "Failed to write to news_items (non-blocking): %s",
                e,
                extra={"type": type, "item_id": item_id},
            )

        # Step 4b: Enqueue for post-processing (translate + image + SEO) — DB-backed
        try:
            publish_pool = _resolve_publish_pool(pool, request)
            if not publish_pool:
                raise RuntimeError("No DB pool available")
            async with publish_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO post_publish_queue (slug, category, source)
                    VALUES ($1, $2, 'intel')
                    ON CONFLICT (slug) DO NOTHING
                    """,
                    article_slug,
                    category,
                )
            logger.info(
                "📥 Enqueued for post-processing",
                extra={"slug": article_slug, "category": category},
            )
        except Exception as e:
            logger.warning("Failed to enqueue post-processing (non-blocking): %s", e)

        # Step 5: Persist the publication attempt without turning a failed
        # GitHub write into an unretryable, falsely-published staging item.
        github_published = bool(github_commit_sha)
        attempt_at = datetime.now(timezone.utc).isoformat()
        if github_published:
            data["publication_requested_at"] = attempt_at
            data["published_url"] = published_url
            data["status"] = "publication_pending"
            data["publish_position"] = body.position if body else "latest"
            data["github_commit_sha"] = github_commit_sha
            if publish_result is not None:
                data["pull_request_number"] = publish_result.pull_request_number
                data["auto_merge_enabled"] = publish_result.auto_merge_enabled
            if mdx_path:
                data["mdx_path"] = mdx_path
            if publish_result is not None and publish_result.image_path:
                data["published_cover_path"] = publish_result.image_path
            data.pop("last_publication_failed_at", None)
            data.pop("publication_lease_until", None)
        else:
            data["status"] = "pending"
            data["last_publication_failed_at"] = attempt_at
            data.pop("published_at", None)
            data.pop("published_url", None)
            data.pop("publication_requested_at", None)
            data.pop("publication_lease_until", None)

        # Persist the honest intermediate state. The external live verifier is
        # the only component allowed to transition this item to ``published``.
        try:
            staging_service.save_staging_item(type, item_id, data)
            logger.info("Staging publication state updated: %s", item_id)
        except Exception as e:
            logger.error("Failed to persist publication state: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Publication request opened but staging state could not be persisted",
            ) from e

        if github_published:
            logger.info(
                "✅ Publish completed (article PR opened, merges after CI passes)",
                extra={
                    "type": type,
                    "item_id": item_id,
                    "title": title,
                    "published_url": published_url,
                    "github_published": True,
                },
            )
            message = (
                "Article queued for publication — pull request opened, "
                "will be live on the site after CI checks pass."
            )
        else:
            # The article is in Qdrant but the MDX never reached GitHub, so it
            # will NOT appear on the website. Surface this honestly to the
            # News Room instead of reporting a false success.
            logger.error(
                "⚠️ Publish incomplete: article ingested to Qdrant but NOT published to "
                "GitHub (MDX not committed) — it will not appear on the website",
                extra={
                    "type": type,
                    "item_id": item_id,
                    "title": title,
                    "github_published": False,
                },
            )
            message = (
                "Article saved to search index but NOT published to the website "
                "(GitHub publish failed). Check backend logs and retry."
            )
            if github_error:
                message = f"{message} Cause: {github_error[:300]}"

        await invalidate_cache("zantara:intel_scraper:*")
        return {
            "success": github_published,
            "github_published": github_published,
            "status": data["status"],
            "message": message,
            "id": item_id,
            "title": title,
            "published_url": published_url if github_published else None,
            "published_at": None,
            "publication_requested_at": data.get("publication_requested_at"),
            "collection": "visa_oracle" if type == "visa" else "bali_intel_bali_news",
            "github_commit_sha": github_commit_sha,
            "pull_request_number": data.get("pull_request_number"),
            "auto_merge_enabled": data.get("auto_merge_enabled"),
            "mdx_path": mdx_path,
            "published_cover_path": data.get("published_cover_path"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Publish failed: %s",
            e,
            exc_info=True,
            extra={"type": type, "item_id": item_id},
        )
        raise HTTPException(status_code=500, detail=str(e)) from e
