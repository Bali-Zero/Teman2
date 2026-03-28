"""
Article Composer API - Manual article creation with Bali Style enrichment

Best Practices 2026 Implementation:
- Retry logic with exponential backoff
- Rate limiting
- Structured error handling
- Input validation
- Caching
- Circuit breaker
- Dependency injection
- Background tasks
- Improved logging

For marketing team to create articles manually with:
- Claude enrichment (Anthropic API)
- Image generation
- SEO optimization
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from prometheus_client import REGISTRY, Counter, Histogram
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.app.core.config import settings
from backend.services.article_composer import (
    APIError,
    ComposeRequestValidator,
    ErrorCode,
    cache_service,
    call_claude_with_retry,
    handle_anthropic_error,
    handle_json_error,
    log_error_with_context,
)

router = APIRouter(prefix="/api/articles", tags=["Article Composer"])
logger = logging.getLogger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# --- PROMETHEUS METRICS ---


def get_or_create_metric(
    metric_class: Any, name: Any, documentation: Any, labelnames: Any = (), **kwargs
) -> Any:
    """Helper to avoid duplicate registration in tests"""
    # Check if metric already exists in the registry
    for collector in REGISTRY._collector_to_names:
        if hasattr(collector, "_name") and collector._name == name:
            return collector
    return metric_class(name, documentation, labelnames, **kwargs)


article_compose_payloads = get_or_create_metric(
    Counter,
    "article_compose_payloads_total",
    "Total article compose requests",
    ["status", "category"],
)

article_compose_duration = get_or_create_metric(
    Histogram,
    "article_compose_duration_seconds",
    "Article composition duration",
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0],
)

article_enrichment_word_count = get_or_create_metric(
    Histogram,
    "article_enrichment_word_count",
    "Word count in facts section",
    ["priority"],
    buckets=[300, 400, 500, 600, 700],
)

article_publish_requests = get_or_create_metric(
    Counter,
    "article_publish_requests_total",
    "Total article publish requests",
    ["status", "has_cover_image"],
)

claude_api_cost_cents = get_or_create_metric(
    Histogram,
    "claude_api_cost_cents",
    "Claude API cost per article (cents)",
    buckets=[1, 2, 5, 10, 20, 50],
)

article_cache_hits = get_or_create_metric(
    Counter,
    "article_cache_hits_total",
    "Total cache hits",
    ["operation"],
)

article_cache_misses = get_or_create_metric(
    Counter,
    "article_cache_misses_total",
    "Total cache misses",
    ["operation"],
)

# --- PYDANTIC MODELS ---


# ComposeRequest is now ComposeRequestValidator (imported from validators)
# Keeping alias for backward compatibility
ComposeRequest = ComposeRequestValidator


class TLDRSection(BaseModel):
    should_worry: str
    what: str
    who: str
    when: str
    risk_level: str


class BaliZeroTake(BaseModel):
    hidden_insight: str
    our_analysis: str
    our_advice: str


class NextSteps(BaseModel):
    expat: list[str]
    investor: list[str]


class EnrichedArticle(BaseModel):
    """Enriched article ready for publication"""

    title: str
    headline: str
    tldr: TLDRSection
    facts: str
    bali_zero_take: BaliZeroTake
    next_steps: NextSteps
    category: str
    priority: str
    relevance_score: int
    ai_summary: str
    ai_tags: list[str]
    suggested_components: list[str]
    cover_image: str | None = None
    source: str
    source_url: str | None
    enriched_at: str


class ComposeResponse(BaseModel):
    """Response from compose endpoint"""

    success: bool
    article: EnrichedArticle | None = None
    error: APIError | str | None = (
        None  # Support both APIError and string for backward compatibility
    )
    api_cost_cents: float = 0
    cached: bool = False
    request_id: str | None = None


# --- ENRICHMENT PROMPT ---

BALIZERO_SYSTEM_PROMPT = """You are the Senior Editor at Bali Zero, an Intelligent Business Operating System for expats and investors in Indonesia.

ROLE:
- You are "L'Insider Intelligente" - the trusted expert who reads boring laws and tells readers only what actually matters
- Think: experienced legal advisor having coffee with a client
- NOT a generic news aggregator or chatbot

AUDIENCE:
- Smart, busy expats and investors in Indonesia
- They hate bureaucracy and want actionable insights
- They ask: "What does this mean for ME?"

TONE GUIDELINES:
- Authoritative but accessible ("Autorevolezza Rilassata")
- Cut the fluff. No "In today's rapidly changing world...". Start with the news.
- Be specific with numbers, dates, requirements
- Add genuine strategic insight, not generic advice

OUTPUT:
You will receive raw article content and transform it into a BaliZero Executive Brief article.
Always respond with valid JSON only (no markdown, no extra text)."""


def build_enrichment_prompt(title: str, content: str, category: str) -> str:
    """Build the prompt for Claude to enrich the article"""
    return f"""{BALIZERO_SYSTEM_PROMPT}

---

## TASK: Transform this into a BaliZero Executive Brief

**Title:** {title}
**Category:** {category}

---

## RAW CONTENT:

{content[:8000]}

---

## OUTPUT FORMAT (STRICT JSON)

{{
  "headline": "<Benefit/Risk-driven headline, max 12 words, in English>",

  "tldr": {{
    "should_worry": "<Yes|No|Depends>",
    "what": "<One line: what happened>",
    "who": "<Who this affects>",
    "when": "<Effective date or timeline>",
    "risk_level": "<High|Medium|Low>"
  }},

  "facts": "<Pure journalism section. What happened, dates, numbers, sources. No opinions. 400-600 words based on news relevance (high priority = 600 words, medium = 500, low = 400). In English.>",

  "bali_zero_take": {{
    "hidden_insight": "<What they don't tell you - 2-3 sentences>",
    "our_analysis": "<Strategic context, non-obvious implications - 3-4 sentences>",
    "our_advice": "<Clear actionable recommendation - 2-3 sentences>"
  }},

  "next_steps": {{
    "expat": ["<Action 1>", "<Action 2>"],
    "investor": ["<Action 1>", "<Action 2>"]
  }},

  "category": "<immigration|business|tax|property|lifestyle|tech|legal>",
  "priority": "<high|medium|low>",
  "relevance_score": <0-100>,

  "ai_summary": "<Executive summary for social/preview, max 280 chars, in English>",
  "ai_tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],

  "suggested_components": ["<component1>", "<component2>"]
}}

NOTES:
- "suggested_components" can include: "timeline", "comparison-table", "decision-tree", "checklist", "risk-meter", "alert-box", "expert-quote"
- For immigration/visa topics, add specific permit types affected
- For tax topics, include specific tax codes (PPh 21, PPh 26, etc.)
- For business topics, mention relevant government bodies (BKPM, OSS, etc.)
- Be SPECIFIC with numbers, dates, and requirements
"""


# --- DEPENDENCY INJECTION ---


def get_request_id() -> str:
    """Generate unique request ID for tracing"""
    return str(uuid.uuid4())


# --- STARTUP/SHUTDOWN EVENTS ---


@router.on_event("startup")
async def startup_event() -> None:
    """Initialize cache service on startup"""
    await cache_service.initialize()


@router.on_event("shutdown")
async def shutdown_event() -> None:
    """Close cache service on shutdown"""
    await cache_service.close()


# --- API ENDPOINTS ---


@router.post("/compose", response_model=ComposeResponse)
@limiter.limit("10/minute")  # Rate limiting: 10 requests per minute per IP
async def compose_article(
    payload: ComposeRequest,  # Body
    request: Request = None,  # type: ignore  # noqa: ARG001 - required by @limiter
    background_tasks: BackgroundTasks = None,  # type: ignore
    request_id: str = Depends(get_request_id),
) -> ComposeResponse:
    """
    Compose/enrich an article with Bali Zero style.

    NOTE: This endpoint is currently disabled. Article composition with Claude/Anthropic
    has been removed. Use alternative enrichment methods.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "error": {
                "code": "SERVICE_DISABLED",
                "message": "Article composer service has been disabled. Claude/Anthropic integration removed.",
            },
            "request_id": request_id,
        },
    )

    # Original implementation disabled - Anthropic/Claude removed
    start_time = time.time()

    # Validate API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        error = APIError.create(
            code=ErrorCode.API_KEY_NOT_CONFIGURED,
            message="ANTHROPIC_API_KEY not configured",
            request_id=request_id,
        )
        article_compose_payloads.labels(status="error", category=payload.category).inc()
        raise HTTPException(status_code=500, detail=error.model_dump())

    # Log request start
    logger.info(
        "Article composition started",
        extra={
            "request_id": request_id,
            "article_title": payload.title,
            "category": payload.category,
            "content_length": len(payload.content),
        },
    )

    try:
        # Check cache first
        cached_result = await cache_service.get_compose_cache(
            payload.title, payload.content, payload.category
        )
        if cached_result:
            logger.info(
                "Cache hit",
                extra={"request_id": request_id, "article_title": payload.title},
            )
            article_cache_hits.labels(operation="compose").inc()
            return ComposeResponse(
                success=True,
                article=EnrichedArticle(**cached_result["article"]),
                api_cost_cents=cached_result.get("api_cost_cents", 0),
                cached=True,
                request_id=request_id,
            )

        article_cache_misses.labels(operation="compose").inc()

        # Build prompt
        prompt = build_enrichment_prompt(
            title=payload.title, content=payload.content, category=payload.category
        )

        # Call Claude with retry logic
        logger.info(
            "Calling Claude API",
            extra={"request_id": request_id, "model": "claude-sonnet-4-20250514"},
        )
        message = await call_claude_with_retry(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
        )

        # Extract response text
        response_text = message.content[0].text

        # Clean JSON from markdown if present
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            error = handle_json_error(e, response_text, payload.title, request_id)
            article_compose_payloads.labels(status="json_error", category=payload.category).inc()
            return ComposeResponse(success=False, error=error, request_id=request_id)

        # Calculate approximate cost (Claude Sonnet: $3/$15 per 1M tokens)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost_cents = input_tokens * 0.0003 + output_tokens * 0.0015  # cents

        # Build enriched article
        enriched = EnrichedArticle(
            title=payload.title,
            headline=data.get("headline", payload.title),
            tldr=TLDRSection(
                **data.get(
                    "tldr",
                    {
                        "should_worry": "Depends",
                        "what": "Article content",
                        "who": "Expats and investors",
                        "when": "Now",
                        "risk_level": "Medium",
                    },
                )
            ),
            facts=data.get("facts", payload.content[:500]),
            bali_zero_take=BaliZeroTake(
                **data.get(
                    "bali_zero_take", {"hidden_insight": "", "our_analysis": "", "our_advice": ""}
                )
            ),
            next_steps=NextSteps(**data.get("next_steps", {"expat": [], "investor": []})),
            category=data.get("category", payload.category),
            priority=data.get("priority", "medium"),
            relevance_score=data.get("relevance_score", 50),
            ai_summary=data.get("ai_summary", ""),
            ai_tags=data.get("ai_tags", []),
            suggested_components=data.get("suggested_components", []),
            cover_image=None,  # Will be provided by frontend during publish
            source=payload.author,
            source_url=payload.source_url,
            enriched_at=datetime.now(timezone.utc).isoformat(),
        )

        # Cache result in background
        cache_data = {
            "article": enriched.model_dump(),
            "api_cost_cents": cost_cents,
        }
        background_tasks.add_task(
            cache_service.set_compose_cache,
            payload.title,
            payload.content,
            payload.category,
            cache_data,
        )

        # Track metrics
        duration = time.time() - start_time
        article_compose_payloads.labels(status="success", category=payload.category).inc()
        article_compose_duration.observe(duration)
        claude_api_cost_cents.observe(cost_cents)

        # Track word count by priority
        facts_word_count = len(enriched.facts.split())
        article_enrichment_word_count.labels(priority=enriched.priority).observe(facts_word_count)

        logger.info(
            "Article enriched successfully",
            extra={
                "request_id": request_id,
                "headline": enriched.headline[:50],
                "cost_cents": cost_cents,
                "duration_seconds": duration,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )

        return ComposeResponse(
            success=True,
            article=enriched,
            api_cost_cents=round(cost_cents, 2),
            cached=False,
            request_id=request_id,
        )

    except anthropic.APIError as e:
        error = handle_anthropic_error(e, payload.title, payload.category, request_id)
        article_compose_payloads.labels(status="api_error", category=payload.category).inc()
        log_error_with_context(
            e,
            {
                "request_id": request_id,
                "article_title": payload.title,
                "category": payload.category,
            },
        )
        raise error from e

    except Exception as e:
        error = APIError.create(
            code=ErrorCode.ENRICHMENT_FAILED,
            message=f"Enrichment failed: {str(e)}",
            details={
                "request_id": request_id,
                "article_title": payload.title,
                "category": payload.category,
            },
            request_id=request_id,
        )
        article_compose_payloads.labels(status="error", category=payload.category).inc()
        log_error_with_context(
            e,
            {
                "request_id": request_id,
                "article_title": payload.title,
                "category": payload.category,
            },
        )
        return ComposeResponse(success=False, error=error, request_id=request_id)


@router.get("/compose/status")
async def compose_status() -> dict[str, Any]:
    """Check if article composer is properly configured"""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    return {
        "configured": bool(api_key),
        "api_key_set": bool(api_key),
        "model": "claude-sonnet-4-20250514",
        "estimated_cost_per_article": "$0.02-0.05",
        "cache_enabled": cache_service.enabled,
        "rate_limit": "10 requests/minute per IP",
    }


# --- PUBLISHING MODELS ---


class PublishRequest(BaseModel):
    """Request to publish an article to the site"""

    article: EnrichedArticle
    cover_image_base64: str | None = Field(
        default=None, description="Cover image as base64 encoded string"
    )
    cover_image_filename: str | None = Field(
        default=None, description="Cover image filename (e.g., 'article-cover.jpg')"
    )
    position: str = Field(default="normal", description="Position: main_featured|secondary|normal")
    slug: str | None = Field(
        default=None, description="Custom slug, auto-generated if not provided"
    )


class PublishResponse(BaseModel):
    """Response from publish endpoint"""

    success: bool
    message: str
    article_url: str | None = None
    mdx_path: str | None = None
    image_path: str | None = None
    commit_sha: str | None = None
    error: str | None = None


def generate_slug(headline: str) -> str:
    """Generate URL-friendly slug from headline"""
    import re

    # Convert to lowercase and replace spaces with hyphens
    slug = headline.lower()
    # Remove special characters except hyphens
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    # Replace spaces with hyphens
    slug = re.sub(r"\s+", "-", slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug[:120]  # Limit slug length


def generate_mdx_content(article: EnrichedArticle, slug: str, cover_image_path: str | None) -> str:
    """Generate MDX file content from enriched article"""
    import json as json_module

    # Map category to URL-friendly format
    category_map = {
        "immigration": "immigration",
        "business": "business",
        "tax": "tax-legal",
        "tax-legal": "tax-legal",
        "property": "property",
        "lifestyle": "lifestyle",
        "tech": "tech",
        "legal": "tax-legal",
    }
    category_slug = category_map.get(article.category, article.category)

    # Generate reading time estimate (avg 200 words per minute)
    word_count = len(article.facts.split()) + len(article.bali_zero_take.our_analysis.split())
    reading_time = max(3, word_count // 200 + 1)

    # Build tags string for frontmatter
    tags_str = ", ".join([f'"{tag}"' for tag in article.ai_tags])

    # Convert next steps to JSON strings for components
    expat_steps_json = json_module.dumps(article.next_steps.expat)
    investor_steps_json = json_module.dumps(article.next_steps.investor)

    # Cover image path
    cover_img = cover_image_path or f"/static/news/{slug}.jpg"

    # Build conditional sections - skip empty Bali Zero Take and Next Steps
    bali_zero_take_section = ""
    has_bzt = (
        article.bali_zero_take.hidden_insight.strip()
        or article.bali_zero_take.our_analysis.strip()
        or article.bali_zero_take.our_advice.strip()
    )
    if has_bzt:
        bali_zero_take_section = "\n---\n\n## Bali Zero Take\n"
        if article.bali_zero_take.hidden_insight.strip():
            bali_zero_take_section += (
                f"\n### The Hidden Insight\n\n{article.bali_zero_take.hidden_insight}\n"
            )
        if article.bali_zero_take.our_analysis.strip():
            bali_zero_take_section += (
                f"\n### Our Analysis\n\n{article.bali_zero_take.our_analysis}\n"
            )
        if article.bali_zero_take.our_advice.strip():
            bali_zero_take_section += f"\n### Our Advice\n\n{article.bali_zero_take.our_advice}\n"

    next_steps_section = ""
    has_steps = article.next_steps.expat or article.next_steps.investor
    if has_steps:
        next_steps_section = f"""
---

## Next Steps

<Checklist
  title="Action Items"
  items={{[
    {{ text: "For Expats", subItems: {expat_steps_json} }},
    {{ text: "For Investors", subItems: {investor_steps_json} }},
  ]}}
/>
"""

    # AI SEO optimization fields
    ai_confidence = getattr(article, "ai_confidence_score", 0.85)
    answer_snippet = getattr(article, "answer_snippet", article.ai_summary)
    primary_question = getattr(
        article, "primary_question", f"What does {article.headline} mean for expats in Bali?"
    )

    # Entity mentions from enrichment
    entity_mentions_yaml = ""
    entities = getattr(article, "entity_mentions", [])
    if entities:
        entity_lines = []
        for ent in entities[:5]:
            name = ent.get("name", "") if isinstance(ent, dict) else str(ent)
            etype = ent.get("type", "Organization") if isinstance(ent, dict) else "Organization"
            entity_lines.append(f"    - name: {name}\n      type: {etype}")
        entity_mentions_yaml = "  entityMentions:\n" + "\n".join(entity_lines)

    mdx_content = f'''---
title: "{article.headline}"
slug: "{slug}"
excerpt: "{article.ai_summary}"
coverImage: "{cover_img}"
coverImageAlt: "{article.headline}"
category: "{category_slug}"
tags: [{tags_str}]
publishedAt: "{datetime.now(timezone.utc).strftime("%Y-%m-%d")}"
author:
  name: "{article.source}"
  avatar: /static/zantara-avatar.png
trending: {str(article.priority == "high").lower()}
featured: false
readingTime: {reading_time}
difficulty: "intermediate"
seoTitle: "{article.headline}"
seoDescription: "{article.ai_summary}"
aiGenerated: true
aiConfidenceScore: {ai_confidence}
aiOptimization:
  answerSnippet: "{answer_snippet}"
  primaryQuestion: "{primary_question}"
{entity_mentions_yaml}
---

## TL;DR

<InfoCard
  title="Quick Summary"
  items={{[
    {{ label: "Should I Worry?", value: "{article.tldr.should_worry}" }},
    {{ label: "Risk Level", value: "{article.tldr.risk_level}" }},
    {{ label: "Who's Affected", value: "{article.tldr.who}" }},
    {{ label: "When", value: "{article.tldr.when}" }},
  ]}}
/>

**{article.tldr.what}**

---

## The Facts

{article.facts}
{bali_zero_take_section}{next_steps_section}
---

<AskZantara
  question="Have questions about this topic?"
  placeholder="Ask Zantara AI for personalized advice..."
/>'''
    return mdx_content


@router.post("/publish", response_model=PublishResponse)
async def publish_article(request: PublishRequest) -> PublishResponse:
    """
    Publish an enriched article to the Bali Zero website.

    Creates MDX file and optionally uploads cover image via GitHub API.
    Triggers Vercel auto-deploy.
    """
    from backend.services.integrations.github_publisher import (
        GitHubPublisherError,
        github_publisher,
    )

    has_cover_image = bool(request.cover_image_base64)

    if not github_publisher.is_configured:
        logger.error("GitHub publisher not configured")
        article_publish_requests.labels(status="error", has_cover_image=str(has_cover_image)).inc()
        return PublishResponse(
            success=False,
            message="GitHub API not configured",
            error="Missing GITHUB_TOKEN environment variable",
        )

    try:
        # Generate slug
        slug = request.slug or generate_slug(request.article.headline)

        # Map category to folder
        category_map = {
            "immigration": "immigration",
            "business": "business",
            "tax": "tax-legal",
            "tax-legal": "tax-legal",
            "property": "property",
            "lifestyle": "lifestyle",
            "tech": "tech",
            "legal": "tax-legal",
        }
        category_folder = category_map.get(request.article.category, request.article.category)

        # Prepare files for atomic commit
        files_to_commit = []
        cover_image_path = None

        # 1. Handle cover image if provided
        if request.cover_image_base64 and request.cover_image_filename:
            import base64

            # Decode base64 image
            image_data = base64.b64decode(request.cover_image_base64)

            # Determine image path
            image_filename = request.cover_image_filename or f"{slug}.jpg"
            image_git_path = f"apps/mouth/public/static/news/{image_filename}"
            cover_image_path = f"/static/news/{image_filename}"

            files_to_commit.append({"path": image_git_path, "content": image_data})
            logger.info(f"Will upload cover image: {image_git_path}")

        # 2. Generate MDX content
        mdx_content = generate_mdx_content(request.article, slug, cover_image_path)
        mdx_git_path = f"apps/mouth/src/content/articles/{category_folder}/{slug}.mdx"

        files_to_commit.append({"path": mdx_git_path, "content": mdx_content})

        # 3. Commit files to GitHub
        commit_message = f"feat(article): Add article '{request.article.headline[:50]}...'\n\nCategory: {category_folder}\nPosition: {request.position}\n\n🤖 Published via Article Composer"

        if len(files_to_commit) == 1:
            # Single file commit
            result = await github_publisher.upload_file(
                path=mdx_git_path, content=mdx_content, message=commit_message
            )
        else:
            # Atomic multi-file commit
            result = await github_publisher.create_commit_with_files(
                files=files_to_commit, message=commit_message
            )

        # Build article URL
        article_url = f"https://balizero.com/{category_folder}/{slug}"

        logger.info(f"✅ Article published: {article_url}")
        logger.info(f"   Commit: {result.get('commit_sha', 'N/A')[:7]}")

        # Trigger IndexNow for faster search engine indexing
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as http_client:
                indexnow_resp = await http_client.post(
                    settings.indexnow_api_url,
                    json={
                        "host": "balizero.com",
                        "key": "2633309a0003ec408c59ec48c952604f",
                        "keyLocation": "https://balizero.com/2633309a0003ec408c59ec48c952604f.txt",
                        "urlList": [article_url],
                    },
                )
                logger.info(f"   IndexNow: {indexnow_resp.status_code}")
        except Exception as e:
            logger.warning(f"   IndexNow failed (non-blocking): {e}")

        # Trigger Google Indexing API for faster Google indexing
        try:
            google_credentials = os.getenv("GOOGLE_INDEXING_CREDENTIALS")
            if google_credentials:
                import json

                from google.auth.transport.requests import Request
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_info(
                    json.loads(google_credentials),
                    scopes=["https://www.googleapis.com/auth/indexing"],
                )
                credentials.refresh(Request())

                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    google_resp = await http_client.post(
                        settings.google_indexing_api_url,
                        headers={"Authorization": f"Bearer {credentials.token}"},
                        json={
                            "url": article_url,
                            "type": "URL_UPDATED",
                        },
                    )
                    logger.info(f"   Google Indexing API: {google_resp.status_code}")
            else:
                logger.info("   Google Indexing API: skipped (no credentials)")
        except Exception as e:
            logger.warning(f"   Google Indexing API failed (non-blocking): {e}")

        # Track metrics
        article_publish_requests.labels(
            status="success", has_cover_image=str(has_cover_image)
        ).inc()

        return PublishResponse(
            success=True,
            message="Article published successfully. Vercel will auto-deploy in ~1 minute.",
            article_url=article_url,
            mdx_path=mdx_git_path,
            image_path=cover_image_path,
            commit_sha=result.get("commit_sha"),
        )

    except GitHubPublisherError as e:
        logger.error(f"GitHub publish error: {e}")
        article_publish_requests.labels(
            status="github_error", has_cover_image=str(has_cover_image)
        ).inc()
        return PublishResponse(success=False, message="Failed to publish to GitHub", error=str(e))
    except Exception as e:
        logger.error(f"Publish failed: {e}", exc_info=True)
        article_publish_requests.labels(status="error", has_cover_image=str(has_cover_image)).inc()
        return PublishResponse(success=False, message="Failed to publish article", error=str(e))


@router.get("/publish/status")
async def publish_status() -> dict[str, Any]:
    """Check if article publishing is properly configured"""
    from backend.app.core.config import settings
    from backend.services.integrations.github_publisher import github_publisher

    return {
        "configured": github_publisher.is_configured,
        "github_token_set": bool(settings.github_token),
        "github_owner": settings.github_owner,
        "github_repo": settings.github_repo,
        "target_branch": "main",
    }
