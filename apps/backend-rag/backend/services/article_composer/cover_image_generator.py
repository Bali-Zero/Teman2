"""
Cover Image Generator — Automatic pipeline for article cover images.

Flow:
  1. Article approved (status → approved) with no image_url
  2. Generator called async (non-blocking) from news router
  3. Generates image via Ideogram v2 API (best quality/cost)
  4. Uploads to Fly.io volume /data/covers/ OR returns Ideogram CDN URL
  5. Updates news_items.image_url in DB

Fallback chain: Ideogram → Unsplash topic search → category default
"""

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category → Unsplash topic mapping (fallback)
# ---------------------------------------------------------------------------
UNSPLASH_TOPICS: dict[str, str] = {
    "business": "business-work",
    "visas": "travel",
    "taxes": "finance",
    "property": "architecture",
    "living": "nature",
    "trends": "technology",
    "general": "business-work",
}

# Category → safe visual concept for Ideogram prompt
CATEGORY_VISUAL: dict[str, str] = {
    "business": "modern office building Bali Indonesia, cinematic golden hour, aerial view",
    "visas": "passport stamps travel documents, cinematic moody lighting, shallow depth of field",
    "taxes": "Indonesian Rupiah banknotes, financial documents, dramatic studio lighting",
    "property": "luxury villa Bali rice terraces, drone aerial shot, sunset glow",
    "living": "Bali sunrise temple silhouette, dramatic sky, long exposure",
    "trends": "modern coworking space Bali, overhead cinematic, warm light",
    "general": "Jakarta skyline Bali Indonesia, cinematic wide angle, blue hour",
}


class CoverImageGenerator:
    """
    Generates cover images for news articles that lack one.
    Called asynchronously; never blocks the article API response.
    """

    def __init__(self) -> None:
        self._ideogram_key = os.getenv("IDEOGRAM_API_KEY")
        self._unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def generate_and_attach(
        self,
        *,
        article_id: str,
        title: str,
        summary: str | None,
        category: str,
        pool: Any,  # asyncpg.Pool
    ) -> str | None:
        """
        Generate cover image for an article and persist image_url to DB.
        Returns the final image URL, or None on failure.
        Non-blocking — called via asyncio.create_task().
        """
        try:
            image_url = await self._generate(title=title, summary=summary, category=category)
            if image_url:
                await self._save_to_db(article_id=article_id, image_url=image_url, pool=pool)
                logger.info(f"[CoverImage] Set image for {article_id}: {image_url[:60]}...")
            return image_url
        except Exception as exc:
            logger.warning(f"[CoverImage] Failed for article {article_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Generation pipeline
    # ------------------------------------------------------------------

    async def _generate(self, *, title: str, summary: str | None, category: str) -> str | None:
        """Try Ideogram, then Unsplash, return URL or None."""
        # 1. Ideogram v2 (best quality)
        if self._ideogram_key:
            url = await self._ideogram(title=title, summary=summary, category=category)
            if url:
                return url

        # 2. Unsplash topic search (free, no generation cost)
        if self._unsplash_key:
            url = await self._unsplash(title=title, category=category)
            if url:
                return url

        logger.warning(f"[CoverImage] All generators failed for: {title[:50]}")
        return None

    async def _ideogram(self, *, title: str, summary: str | None, category: str) -> str | None:
        """Generate via Ideogram v2 API."""
        try:
            prompt = self._build_prompt(title=title, summary=summary, category=category)
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    "https://api.ideogram.ai/generate",
                    headers={
                        "Api-Key": self._ideogram_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "image_request": {
                            "prompt": prompt,
                            "aspect_ratio": "ASPECT_16_9",
                            "model": "V_2",
                            "magic_prompt_option": "AUTO",
                            "style_type": "REALISTIC",
                            "negative_prompt": "text, watermark, logo, title overlay, person face, nsfw",
                        }
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                images = data.get("data", [])
                if images:
                    return images[0].get("url")
        except Exception as exc:
            logger.debug(f"[CoverImage] Ideogram error: {exc}")
        return None

    async def _unsplash(self, *, title: str, category: str) -> str | None:
        """Search Unsplash for a relevant landscape/editorial photo."""
        try:
            topic = UNSPLASH_TOPICS.get(category, "business-work")
            # Use key terms from title for better relevance
            keywords = self._extract_keywords(title)
            query = f"{keywords} {topic} Bali Indonesia" if keywords else f"Bali Indonesia {topic}"

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.unsplash.com/photos/random",
                    headers={"Authorization": f"Client-ID {self._unsplash_key}"},
                    params={
                        "query": query,
                        "orientation": "landscape",
                        "content_filter": "high",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Use regular size (1080px wide, free license)
                    return data.get("urls", {}).get("regular")
        except Exception as exc:
            logger.debug(f"[CoverImage] Unsplash error: {exc}")
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, *, title: str, summary: str | None, category: str) -> str:
        """Craft a photorealistic Ideogram prompt from article metadata."""
        visual_base = CATEGORY_VISUAL.get(category, CATEGORY_VISUAL["general"])
        # Strip common filler words from title for cleaner prompt
        clean_title = re.sub(
            r"\b(what|how|why|when|the|a|an|in|of|for|and|or|to|is|are|was|were)\b",
            "",
            title.lower(),
            flags=re.IGNORECASE,
        ).strip()
        # Take first 6 significant words
        title_keywords = " ".join(clean_title.split()[:6])

        parts = [
            f"Editorial magazine cover photo: {title_keywords},",
            visual_base + ",",
            "ultra-high resolution, professional photography, cinematic color grading,",
            "dramatic contrast, no text overlay, no watermark",
        ]
        return " ".join(parts)

    @staticmethod
    def _extract_keywords(title: str) -> str:
        """Extract 3-5 significant nouns from a title for Unsplash search."""
        stop = {
            "the", "a", "an", "in", "of", "for", "and", "or", "to", "is", "are",
            "was", "were", "what", "how", "why", "when", "who", "which", "with",
            "from", "that", "this", "will", "have", "has", "its", "do", "does",
        }
        words = [w for w in re.sub(r"[^\w\s]", "", title.lower()).split() if w not in stop]
        return " ".join(words[:4])

    @staticmethod
    async def _save_to_db(*, article_id: str, image_url: str, pool: Any) -> None:
        """Persist generated image_url to news_items table."""
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE news_items SET image_url = $1 WHERE id = $2 AND image_url IS NULL",
                image_url,
                article_id,
            )


# Module-level singleton — imported by news router
_generator: CoverImageGenerator | None = None


def get_cover_image_generator() -> CoverImageGenerator:
    global _generator
    if _generator is None:
        _generator = CoverImageGenerator()
    return _generator


async def trigger_cover_generation(
    *,
    article_id: str,
    title: str,
    summary: str | None,
    category: str,
    image_url: str | None,
    pool: Any,
) -> None:
    """
    Non-blocking fire-and-forget: generate cover if missing.
    Called via asyncio.create_task() from news router.
    """
    if image_url:
        return  # Already has a cover — skip
    gen = get_cover_image_generator()
    await gen.generate_and_attach(
        article_id=article_id,
        title=title,
        summary=summary,
        category=category,
        pool=pool,
    )
