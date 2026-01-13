"""
Article Composer API - Manual article creation with Bali Style enrichment

For marketing team to create articles manually with:
- Claude enrichment (Anthropic API)
- Image generation
- SEO optimization
"""

import os
import logging
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import anthropic

router = APIRouter(prefix="/api/articles", tags=["Article Composer"])
logger = logging.getLogger(__name__)

# --- PYDANTIC MODELS ---

class ComposeRequest(BaseModel):
    """Request to compose/enrich an article"""
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Raw article content")
    category: str = Field(default="business", description="Category: immigration|business|tax|property|lifestyle|tech|legal")
    source_url: Optional[str] = Field(default=None, description="Original source URL if any")
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
    expat: List[str]
    investor: List[str]


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
    ai_tags: List[str]
    suggested_components: List[str]
    cover_image: Optional[str] = None
    image_prompt: Optional[str] = None
    source: str
    source_url: Optional[str]
    enriched_at: str


class ComposeResponse(BaseModel):
    """Response from compose endpoint"""
    success: bool
    article: Optional[EnrichedArticle] = None
    error: Optional[str] = None
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

async def generate_cover_image(headline: str, category: str, summary: str) -> Dict[str, Any]:
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
        "prompt": image_prompt
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
            title=request.title,
            content=request.content,
            category=request.category
        )

        # Call Claude
        logger.info("Calling Claude API for enrichment...")
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
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
            summary=data.get("ai_summary", "")
        )

        # Calculate approximate cost (Claude Sonnet: $3/$15 per 1M tokens)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost_cents = (input_tokens * 0.0003 + output_tokens * 0.0015)  # cents

        # Build enriched article
        enriched = EnrichedArticle(
            title=request.title,
            headline=data.get("headline", request.title),
            tldr=TLDRSection(**data.get("tldr", {
                "should_worry": "Depends",
                "what": "Article content",
                "who": "Expats and investors",
                "when": "Now",
                "risk_level": "Medium"
            })),
            facts=data.get("facts", request.content[:500]),
            bali_zero_take=BaliZeroTake(**data.get("bali_zero_take", {
                "hidden_insight": "",
                "our_analysis": "",
                "our_advice": ""
            })),
            next_steps=NextSteps(**data.get("next_steps", {
                "expat": [],
                "investor": []
            })),
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
            enriched_at=datetime.utcnow().isoformat()
        )

        logger.info(f"✅ Article enriched: {enriched.headline[:50]}...")
        logger.info(f"   Cost: ${cost_cents/100:.4f} ({input_tokens} in, {output_tokens} out)")

        return ComposeResponse(
            success=True,
            article=enriched,
            api_cost_cents=round(cost_cents, 2)
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.debug(f"Raw response: {response_text[:500] if 'response_text' in dir() else 'N/A'}")
        return ComposeResponse(
            success=False,
            error=f"Failed to parse Claude response: {str(e)}"
        )
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return ComposeResponse(
            success=False,
            error=f"Claude API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        return ComposeResponse(
            success=False,
            error=str(e)
        )


@router.get("/compose/status")
async def compose_status():
    """Check if article composer is properly configured"""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    return {
        "configured": bool(api_key),
        "api_key_set": bool(api_key),
        "model": "claude-sonnet-4-20250514",
        "estimated_cost_per_article": "$0.02-0.05"
    }
