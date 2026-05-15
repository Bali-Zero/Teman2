"""
Dream Thinking Room Router
Handles AI generation, content scraping, and state persistence for the Dream Room.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

# Reuse existing AI service utilities if available, or import standard ones
# Assuming call_claude_with_retry is available in article_composer service for now
# Ideally we should move it to a shared LLM service
from backend.services.article_composer import call_claude_with_retry

router = APIRouter(prefix="/api/dream", tags=["Dream Room"])
logger = logging.getLogger(__name__)

# --- Pydantic Models for State ---


class Inspiration(BaseModel):
    id: str
    type: str  # 'image', 'text', 'link', 'color'
    content: str
    metadata: dict[str, Any] = {}
    position: dict[str, float] | None = None


class ScrapingRequest(BaseModel):
    url: str


class ScrapingResponse(BaseModel):
    title: str
    keyPoints: list[str]
    quotes: list[dict[str, str]]
    success: bool


class GenerateRequest(BaseModel):
    prompt: str
    context: str = ""
    mode: str = "expand"  # expand, rewrite, shorten, tone-shift


class GenerateResponse(BaseModel):
    text: str
    success: bool


# Simple in-memory store for demo persistence if DB not ready
# In production, use Redis or Postgres
MOCK_DB: dict[str, Any] = {}

# --- Endpoints ---


@router.post("/state")
async def save_state(user_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Persist Dream Room state (Articles, Inspirations, etc.)"""
    # TODO(#77): Replace in-memory MOCK_DB with Postgres JSONB persistence.
    MOCK_DB[user_id] = state
    logger.info(f"Saved state for user {user_id}")
    return {
        "success": True,
        "timestamp": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
    }


@router.get("/state/{user_id}")
async def get_state(user_id: str) -> dict[str, Any]:
    """Retrieve persisted state"""
    state = MOCK_DB.get(user_id)
    return {"success": True, "state": state}


@router.post("/scrape", response_model=ScrapingResponse)
async def scrape_url(request: ScrapingRequest) -> dict[str, Any]:
    """
    Fetch a URL and extract title + key paragraphs + quotes.

    Closes TODO(#78): uses ``httpx + BeautifulSoup`` (no paid Firecrawl
    dependency). Failures degrade to ``success=False`` rather than 500,
    so the Dream Room can render a graceful "couldn't read this page"
    state.
    """
    from backend.services.scraping.url_scraper import (
        scrape_url as _scrape_url_impl,
    )

    try:
        content = await _scrape_url_impl(request.url)
    except ValueError as e:
        # Invalid URL scheme — let FastAPI map this to a 400.
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "title": content.title,
        "keyPoints": content.keyPoints,
        "quotes": content.quotes,
        "success": content.success,
    }


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest) -> dict[str, Any]:
    """
    Generate content using Claude.
    """
    try:
        system_prompt = "You are an expert editor and creative writing assistant."
        user_prompt = f"Task: {request.mode}\nContext: {request.context}\nInput: {request.prompt}"

        # Reuse existing Claude wrapper
        message = await call_claude_with_retry(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            model="claude-3-5-sonnet-20240620",  # or latest configured
            max_tokens=1024,
        )

        return {"text": message.content[0].text, "success": True}
    except Exception as e:
        logger.error(f"AI Generation failed: {e}")
        return {"text": "AI generation unavailable momentarily.", "success": False}
