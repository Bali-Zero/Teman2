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
    # TODO: Replace with real DB call (e.g. Postgres JSONB or Redis)
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
    Mock scraper for now.
    TODO: Integrate with Firecrawl or standard BeautifulSoup scraper.
    """
    # Mock delay
    import asyncio

    await asyncio.sleep(1.5)

    return {
        "title": "The Future of AI in Content Marketing (Scraped)",
        "keyPoints": [
            "AI tools are increasing production speed",
            "Human creativity is the differentiator",
            f"Scraped content from {request.url}",
        ],
        "quotes": [
            {"text": "AI is a tool, not a master.", "author": "Tech Visionary"},
            {"text": "Content is king, context is queen.", "author": "Marketing Guru"},
        ],
        "success": True,
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
