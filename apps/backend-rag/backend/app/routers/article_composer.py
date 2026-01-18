"""
Article Composer API - Manual article creation with Bali Style enrichment

For marketing team to create articles manually with:
- Claude enrichment (Anthropic API)
- Image generation
- SEO optimization
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/articles", tags=["Article Composer"])
logger = logging.getLogger(__name__)

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
    image_prompt: str | None = None
    source: str
    source_url: str | None
    enriched_at: str


class ComposeResponse(BaseModel):
    """Response from compose endpoint"""

    success: bool
    article: EnrichedArticle | None = None
    error: str | None = None
    api_cost_cents: float = 0


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

  "facts": "<Pure journalism section. What happened, dates, numbers, sources. No opinions. 200-300 words. In English.>",

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


# --- IMAGE GENERATION ---


async def generate_cover_image(headline: str, category: str, summary: str) -> dict[str, Any]:
    """
    Generate cover image using available image generation service.
    Returns dict with image_path and prompt_used.
    """
    # For now, we'll return a placeholder and let frontend handle image generation
    # In production, this would call Imagen API or similar

    # Build a prompt that could be used for image generation
    image_prompt = f"""Professional editorial cover image for article about: {headline}

Style: Modern, clean, editorial photography style
Theme: {category} in Indonesia/Bali context
Mood: Professional, trustworthy, insightful
Format: 16:9 landscape, suitable for blog header

Key elements to include based on topic:
- If immigration/visa: passport, documents, Indonesia landmarks
- If business: modern office, Jakarta skyline, business meeting
- If tax: financial documents, calculator, professional setting
- If property: Bali villa, real estate, tropical architecture
- If lifestyle: Bali scenery, expat life, tropical living
- If tech: modern devices, digital nomad setup

No text overlays. High quality, photorealistic."""

    return {
        "image_path": None,  # Frontend will generate
        "prompt": image_prompt,
    }


# --- API ENDPOINTS ---


@router.post("/compose", response_model=ComposeResponse)
async def compose_article(request: ComposeRequest):
    """
    Compose/enrich an article with Bali Zero style using Anthropic API.

    Transforms raw content into a complete BaliZero Executive Brief with:
    - Strategic headline
    - TL;DR section
    - Facts (pure journalism)
    - BaliZero Take (strategic analysis)
    - Next steps by profile
    - AI tags and summary
    - Image generation prompt
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        raise HTTPException(status_code=500, detail="API key not configured")

    logger.info(f"Composing article: {request.title[:50]}...")

    try:
        # Initialize Anthropic client
        client = anthropic.Anthropic(api_key=api_key)

        # Build prompt
        prompt = build_enrichment_prompt(
            title=request.title, content=request.content, category=request.category
        )

        # Call Claude
        logger.info("Calling Claude API for enrichment...")
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
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
        data = json.loads(response_text)

        # Generate image prompt
        image_result = await generate_cover_image(
            headline=data.get("headline", request.title),
            category=data.get("category", request.category),
            summary=data.get("ai_summary", ""),
        )

        # Calculate approximate cost (Claude Sonnet: $3/$15 per 1M tokens)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost_cents = input_tokens * 0.0003 + output_tokens * 0.0015  # cents

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
                    "bali_zero_take", {"hidden_insight": "", "our_analysis": "", "our_advice": ""}
                )
            ),
            next_steps=NextSteps(**data.get("next_steps", {"expat": [], "investor": []})),
            category=data.get("category", request.category),
            priority=data.get("priority", "medium"),
            relevance_score=data.get("relevance_score", 50),
            ai_summary=data.get("ai_summary", ""),
            ai_tags=data.get("ai_tags", []),
            suggested_components=data.get("suggested_components", []),
            cover_image=image_result.get("image_path"),
            image_prompt=image_result.get("prompt"),
            source=request.author,
            source_url=request.source_url,
            enriched_at=datetime.utcnow().isoformat(),
        )

        logger.info(f"✅ Article enriched: {enriched.headline[:50]}...")
        logger.info(f"   Cost: ${cost_cents / 100:.4f} ({input_tokens} in, {output_tokens} out)")

        return ComposeResponse(success=True, article=enriched, api_cost_cents=round(cost_cents, 2))

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.debug(f"Raw response: {response_text[:500] if 'response_text' in dir() else 'N/A'}")
        return ComposeResponse(success=False, error=f"Failed to parse Claude response: {str(e)}")
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return ComposeResponse(success=False, error=f"Claude API error: {str(e)}")
    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        return ComposeResponse(success=False, error=str(e))


@router.get("/compose/status")
async def compose_status():
    """Check if article composer is properly configured"""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    return {
        "configured": bool(api_key),
        "api_key_set": bool(api_key),
        "model": "claude-sonnet-4-20250514",
        "estimated_cost_per_article": "$0.02-0.05",
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
    return slug[:60]  # Limit slug length


def generate_mdx_content(article: EnrichedArticle, slug: str, cover_image_path: str | None) -> str:
    """Generate MDX file content from enriched article"""
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

    # Build tags string
    tags_str = ", ".join([f'"{tag}"' for tag in article.ai_tags])

    # Cover image path
    cover_img = cover_image_path or f"/static/news/{slug}.jpg"

    mdx_content = f'''---
title: "{article.headline}"
slug: "{slug}"
excerpt: "{article.ai_summary}"
coverImage: "{cover_img}"
coverImageAlt: "{article.headline}"
category: "{category_slug}"
tags: [{tags_str}]
publishedAt: "{datetime.utcnow().strftime("%Y-%m-%d")}"
author: "{article.source}"
trending: {str(article.priority == "high").lower()}
featured: false
readingTime: {reading_time}
difficulty: "intermediate"
seoTitle: "{article.headline}"
seoDescription: "{article.ai_summary}"
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

---

## Bali Zero Take

### The Hidden Insight

{article.bali_zero_take.hidden_insight}

### Our Analysis

{article.bali_zero_take.our_analysis}

### Our Advice

{article.bali_zero_take.our_advice}

---

## Next Steps

<Checklist
  title="Action Items"
  items={{[
    {{ text: "For Expats", subItems: {article.next_steps.expat} }},
    {{ text: "For Investors", subItems: {article.next_steps.investor} }},
  ]}}
/>

---

<AskZantara
  question="Have questions about this topic?"
  placeholder="Ask Zantara AI for personalized advice..."
/>
'''
    return mdx_content


@router.post("/publish", response_model=PublishResponse)
async def publish_article(request: PublishRequest):
    """
    Publish an enriched article to the Bali Zero website.

    Creates MDX file and optionally uploads cover image via GitHub API.
    Triggers Vercel auto-deploy.
    """
    from backend.services.integrations.github_publisher import (
        GitHubPublisherError,
        github_publisher,
    )

    if not github_publisher.is_configured:
        logger.error("GitHub publisher not configured")
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
        return PublishResponse(success=False, message="Failed to publish to GitHub", error=str(e))
    except Exception as e:
        logger.error(f"Publish failed: {e}", exc_info=True)
        return PublishResponse(success=False, message="Failed to publish article", error=str(e))


@router.get("/publish/status")
async def publish_status():
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
