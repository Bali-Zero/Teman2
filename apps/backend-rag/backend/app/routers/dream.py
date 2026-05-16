"""
Dream Thinking Room Router
Handles AI generation, content scraping, and state persistence for the Dream Room.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.deps.database import get_database_pool

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


# --- Endpoints ---


@router.post("/state")
async def save_state(
    user_id: str,
    state: dict[str, Any],
    pool=Depends(get_database_pool),
) -> dict[str, Any]:
    """Persist Dream Room state (Articles, Inspirations, etc.) to Postgres.

    Closes TODO(#77): replaced the in-memory MOCK_DB (which silently lost
    state on every Fly machine restart) with a JSONB-backed UPSERT in
    table ``dream_room_state`` (migration 178).

    The asyncpg pool installs a ``jsonb`` codec in
    ``init_db_connection`` — we pass ``state`` as a Python dict and let
    the codec serialize it once. Passing ``json.dumps(state)`` here would
    double-encode (cf. memory:
    ``discovery_jsonb_double_encoding_systemic_2026_05_14``).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dream_room_state (user_id, state)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
              SET state = EXCLUDED.state,
                  updated_at = NOW()
            """,
            user_id,
            state,  # dict, NOT json.dumps(state) — codec handles serialization.
        )
    logger.info("Saved Dream Room state user=%s", user_id)
    return {
        "success": True,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/state/{user_id}")
async def get_state(
    user_id: str,
    pool=Depends(get_database_pool),
) -> dict[str, Any]:
    """Retrieve persisted Dream Room state (TODO #77).

    Returns ``state=None`` when the user has no saved canvas — keeps the
    client contract compatible with the legacy MOCK_DB.get() behaviour.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT state FROM dream_room_state WHERE user_id = $1",
            user_id,
        )

    state = row["state"] if row is not None else None
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
