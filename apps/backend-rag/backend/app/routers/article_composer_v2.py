"""
Article Composer API v2 - Best Practices 2026 Implementation

Improvements:
- Retry logic with exponential backoff
- Rate limiting
- Structured error handling
- Input validation
- Caching
- Circuit breaker
- Dependency injection
- Background tasks
- Improved logging
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from backend.services.article_composer import (
    APIError,
    ErrorCode,
    cache_service,
    call_claude_with_retry,
    handle_anthropic_error,
    handle_json_error,
    log_error_with_context,
)
from backend.services.article_composer.validators import ComposeRequestValidator

router = APIRouter(prefix="/api/articles", tags=["Article Composer"])
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
router.state.limiter = limiter
router.add_exception_handler(HTTPException, _rate_limit_exceeded_handler)

# --- PROMETHEUS METRICS ---

article_compose_requests = Counter(
    "article_compose_requests_total",
    "Total article compose requests",
    ["status", "category"],
)

article_compose_duration = Histogram(
    "article_compose_duration_seconds",
    "Article composition duration",
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0],
)

article_enrichment_word_count = Histogram(
    "article_enrichment_word_count",
    "Word count in facts section",
    ["priority"],
    buckets=[300, 400, 500, 600, 700],
)

article_publish_requests = Counter(
    "article_publish_requests_total",
    "Total article publish requests",
    ["status", "has_cover_image"],
)

claude_api_cost_cents = Histogram(
    "claude_api_cost_cents",
    "Claude API cost per article (cents)",
    buckets=[1, 2, 5, 10, 20, 50],
)

article_cache_hits = Counter(
    "article_cache_hits_total",
    "Total cache hits",
    ["operation"],
)

article_cache_misses = Counter(
    "article_cache_misses_total",
    "Total cache misses",
    ["operation"],
)

# --- PYDANTIC MODELS ---


class ComposeRequest(BaseModel):
    """Request to compose/enrich an article"""

    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Raw article content")
    category: str = Field(
        default="business",
        description="Category: immigration|business|tax|property|lifestyle|tech|legal",
    )
    source_url: str | None = Field(default=None, description="Original source URL if any")
    author: str = Field(default="Marketing Team", description="Author name")


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
    error: APIError | None = None
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


# --- API ENDPOINTS ---


@router.post("/compose", response_model=ComposeResponse)
@limiter.limit("10/minute")  # Rate limiting: 10 requests per minute per IP
async def compose_article(
    request: ComposeRequestValidator,
    background_tasks: BackgroundTasks,
    req: Request,
    request_id: str = Depends(get_request_id),
):
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
        article_compose_requests.labels(status="error", category=request.category).inc()
        raise HTTPException(status_code=500, detail=error.model_dump())

    # Log request start
    logger.info(
        "Article composition started",
        extra={
            "request_id": request_id,
            "article_title": request.title,
            "category": request.category,
            "content_length": len(request.content),
        },
    )

    try:
        # Check cache first
        cached_result = await cache_service.get_compose_cache(
            request.title, request.content, request.category
        )
        if cached_result:
            logger.info(
                "Cache hit",
                extra={"request_id": request_id, "article_title": request.title},
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
            title=request.title, content=request.content, category=request.category
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
            error = handle_json_error(e, response_text, request.title, request_id)
            article_compose_requests.labels(status="json_error", category=request.category).inc()
            return ComposeResponse(success=False, error=error, request_id=request_id)

        # Calculate cost
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost_cents = input_tokens * 0.0003 + output_tokens * 0.0015

        # Build enriched article
        enriched = EnrichedArticle(
            title=request.title,
            headline=data.get("headline", request.title),
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
            facts=data.get("facts", request.content[:500]),
            bali_zero_take=BaliZeroTake(
                **data.get(
                    "bali_zero_take",
                    {"hidden_insight": "", "our_analysis": "", "our_advice": ""},
                )
            ),
            next_steps=NextSteps(**data.get("next_steps", {"expat": [], "investor": []})),
            category=data.get("category", request.category),
            priority=data.get("priority", "medium"),
            relevance_score=data.get("relevance_score", 50),
            ai_summary=data.get("ai_summary", ""),
            ai_tags=data.get("ai_tags", []),
            suggested_components=data.get("suggested_components", []),
            cover_image=None,
            source=request.author,
            source_url=request.source_url,
            enriched_at=datetime.utcnow().isoformat(),
        )

        # Cache result
        cache_data = {
            "article": enriched.model_dump(),
            "api_cost_cents": cost_cents,
        }
        background_tasks.add_task(
            cache_service.set_compose_cache,
            request.title,
            request.content,
            request.category,
            cache_data,
        )

        # Track metrics
        duration = time.time() - start_time
        article_compose_requests.labels(status="success", category=request.category).inc()
        article_compose_duration.observe(duration)
        claude_api_cost_cents.observe(cost_cents)

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
        error = handle_anthropic_error(e, request.title, request.category, request_id)
        article_compose_requests.labels(status="api_error", category=request.category).inc()
        log_error_with_context(
            e,
            {
                "request_id": request_id,
                "article_title": request.title,
                "category": request.category,
            },
        )
        raise error

    except Exception as e:
        error = APIError.create(
            code=ErrorCode.ENRICHMENT_FAILED,
            message=f"Enrichment failed: {str(e)}",
            details={
                "request_id": request_id,
                "article_title": request.title,
                "category": request.category,
            },
            request_id=request_id,
        )
        article_compose_requests.labels(status="error", category=request.category).inc()
        log_error_with_context(
            e,
            {
                "request_id": request_id,
                "article_title": request.title,
                "category": request.category,
            },
        )
        return ComposeResponse(success=False, error=error, request_id=request_id)


@router.get("/compose/status")
async def compose_status():
    """Check if article composer is properly configured"""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    return {
        "configured": bool(api_key),
        "api_key_set": bool(api_key),
        "model": "claude-sonnet-4-20250514",
        "estimated_cost_per_article": "$0.02-0.05",
        "cache_enabled": cache_service.enabled,
    }


# --- PUBLISHING MODELS (keeping existing implementation) ---

# ... (rest of the file with publish endpoints, keeping existing implementation)
