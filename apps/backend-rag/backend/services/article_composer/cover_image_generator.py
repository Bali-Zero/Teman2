"""
Cover Image Generator v2 — High-quality editorial cover images using Bali Zero visual identity.

Flow:
  1. Article published (news_items or intel scraper)
  2. bz_image_style generates cinematic prompt (Claude Haiku visual director + mood + camera/lens)
  3. Fireworks.ai Flux Dev generates image (1344x768) → downloaded as JPG
  4. Image committed to GitHub via post_publish_poller OR saved to DB as /static/news/{slug}.jpg
  5. news_items.image_url updated in DB

Primary:   Fireworks.ai Flux Dev (high quality, 1344x768)
Fallback:  Pollinations.ai (free, decent quality)
Last:      Category default static images

v1 used Ideogram V_2 with weak generic prompts and stored CDN URLs that expire.
v2 uses bz_image_style (Claude Haiku + mood classification + camera/lens + teal/amber brand identity).
"""

import hashlib
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category fallback images (static, always available)
# ---------------------------------------------------------------------------
CATEGORY_DEFAULTS: dict[str, str] = {
    "business": "/static/blog/business-cover.jpg",
    "visas": "/static/blog/visas-cover.jpg",
    "immigration": "/static/blog/visas-cover.jpg",
    "taxes": "/static/blog/taxes-cover.jpg",
    "tax": "/static/blog/taxes-cover.jpg",
    "tax-legal": "/static/blog/taxes-cover.jpg",
    "property": "/static/blog/property-cover.jpg",
    "living": "/static/blog/living-cover.jpg",
    "lifestyle": "/static/blog/living-cover.jpg",
    "trends": "/static/blog/trends-cover.jpg",
    "general": "/static/blog/business-cover.jpg",
}


def _build_prompt_fallback(title: str, category: str, summary: str | None) -> str:
    """Build a decent prompt without bz_image_style (e.g., on Fly.io where Claude CLI is absent).

    Uses the same teal/amber brand identity and cinematic style but without LLM prompt generation.
    """
    import re

    # Category visual concepts (teal/amber brand-aligned)
    visuals: dict[str, str] = {
        "business": "modern glass office in Bali with jungle views, golden hour streaming through windows",
        "visas": "Indonesian KITAS permit card on dark teak desk beside Balinese canang sari offering",
        "immigration": "crowded airport immigration hall, documentary realism, overhead fluorescent",
        "taxes": "cascade of Indonesian Rupiah banknotes on dark volcanic stone, macro shot",
        "tax": "Indonesian tax documents spread on mahogany desk, laptop screen glow",
        "tax-legal": "ancient brass scales on dark surface, Balinese offering flowers as counterweight",
        "property": "stunning luxury Bali villa with infinity pool merging into rice terrace valley",
        "living": "digital nomad in bamboo coworking space, golden afternoon light through bamboo walls",
        "lifestyle": "mixed family walking on Bali black sand beach at golden hour",
        "trends": "aerial Canggu district at golden hour, motorbike light trails below",
        "regulation": "massive stack of Indonesian government forms, single golden beam from skylight",
        "general": "ornate Balinese temple gate at golden hour, mist and volumetric light",
    }

    visual = visuals.get(category, visuals["general"])

    # Extract meaningful words from title
    stop = {
        "the", "a", "an", "in", "of", "for", "and", "or", "to", "is", "are",
        "was", "were", "what", "how", "why", "when", "who", "which", "with",
        "from", "that", "this", "will", "have", "has", "its", "do", "does",
        "new", "your", "must", "now", "can",
    }
    words = [w for w in re.sub(r"[^\w\s]", "", title.lower()).split() if w not in stop]
    keywords = " ".join(words[:5])

    return (
        f"{visual}, {keywords}, "
        "shot on ARRI Alexa Mini LF with 35mm lens, "
        "cinematic teal and amber color grading, "
        "golden hour warm amber sunlight, volumetric light rays, "
        "hyper-realistic, editorial photography, subtle film grain, "
        "no text, no watermark, no logo, no illustration"
    )


def build_prompt(title: str, category: str, summary: str | None) -> str:
    """Build image generation prompt. Tries bz_image_style first, fallback if unavailable."""
    try:
        # bz_image_style lives in bali-intel-scraper/scripts/
        import importlib
        import sys
        from pathlib import Path

        scraper_scripts = Path(__file__).parent.parent.parent.parent.parent / "bali-intel-scraper" / "scripts"
        if str(scraper_scripts) not in sys.path:
            sys.path.insert(0, str(scraper_scripts))

        bz = importlib.import_module("bz_image_style")
        prompt = bz.build_cover_prompt(
            title=title,
            category=category,
            summary=summary,
        )
        logger.info(f"[CoverImage] bz_image_style prompt generated ({len(prompt)} chars)")
        return prompt
    except Exception as exc:
        logger.info(f"[CoverImage] bz_image_style unavailable ({exc}), using fallback prompt")
        return _build_prompt_fallback(title, category, summary)


class CoverImageGenerator:
    """
    Generates high-quality cover images for articles using Bali Zero visual identity.
    Called asynchronously; never blocks the article API response.
    """

    def __init__(self) -> None:
        self._fireworks_key = os.getenv("FIREWORKS_API_KEY")
        self._ideogram_key = os.getenv("IDEOGRAM_API_KEY")
        # Persistent HTTP client (Golden Rule #10). Opening an AsyncClient per
        # call forfeits TLS session resumption and connection pooling — at
        # our article-cover generation rate (minutes apart) that's fine in
        # latency terms, but 3 distinct `async with httpx.AsyncClient(...)`
        # blocks in this file forced a new TCP+TLS handshake every time.
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-create the shared async client.

        Not called from __init__ because there's no running loop yet at
        construction time in some call sites (router module import).
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=90.0,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            )
        return self._client

    async def aclose(self) -> None:
        """Close the internal async client. Safe to call multiple times."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

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
        slug: str | None = None,
        pool: Any,  # asyncpg.Pool
    ) -> str | None:
        """
        Generate cover image and persist image_url to DB.
        Returns the final image URL/path, or None on failure.
        """
        try:
            result = await self._generate(
                title=title, summary=summary, category=category, slug=slug,
            )
            if result:
                image_url = result["url"]
                await self._save_to_db(article_id=article_id, image_url=image_url, pool=pool)
                logger.info(f"[CoverImage] Set image for {article_id}: {image_url[:80]}")
            return result["url"] if result else None
        except Exception as exc:
            logger.warning(f"[CoverImage] Failed for article {article_id}: {exc}")
            return None

    async def generate_bytes(
        self,
        *,
        title: str,
        summary: str | None,
        category: str,
        slug: str | None = None,
    ) -> dict | None:
        """Generate cover image and return bytes + metadata (no DB write).

        Used by post_publish_poller to get the raw image for GitHub commit.
        Returns: {"bytes": b"...", "prompt": "...", "provider": "fireworks|pollinations"}
        or None on failure.
        """
        prompt = build_prompt(title, category, summary)

        # 1. Fireworks.ai Flux Dev
        if self._fireworks_key:
            img_bytes = await self._fireworks(prompt)
            if img_bytes:
                return {"bytes": img_bytes, "prompt": prompt, "provider": "fireworks"}

        # 2. Pollinations.ai fallback (free)
        img_bytes = await self._pollinations(prompt)
        if img_bytes:
            return {"bytes": img_bytes, "prompt": prompt, "provider": "pollinations"}

        logger.warning(f"[CoverImage] All generators failed for: {title[:50]}")
        return None

    # ------------------------------------------------------------------
    # Generation pipeline
    # ------------------------------------------------------------------

    async def _generate(
        self,
        *,
        title: str,
        summary: str | None,
        category: str,
        slug: str | None = None,
    ) -> dict | None:
        """Generate image, return {"url": ..., "bytes": ..., "prompt": ...} or None."""
        result = await self.generate_bytes(
            title=title, summary=summary, category=category, slug=slug,
        )
        if not result:
            return None

        # For DB-only path (news router), store as path reference
        # The actual file is committed to GitHub by post_publish_poller
        if slug:
            url = f"/static/news/{slug}.jpg"
        else:
            # Fallback: use a hash-based filename. MD5 is non-cryptographic
            # here — just a deterministic short id for filenames.
            name_hash = hashlib.md5(title.encode(), usedforsecurity=False).hexdigest()[:12]
            url = f"/static/news/{name_hash}.jpg"

        return {"url": url, "bytes": result["bytes"], "prompt": result["prompt"]}

    async def _fireworks(self, prompt: str) -> bytes | None:
        """Generate via Fireworks.ai Flux Dev API. Returns raw JPEG bytes."""
        client = self._get_client()
        try:
            resp = await client.post(
                "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image",
                headers={
                    "Authorization": f"Bearer {self._fireworks_key}",
                    "Content-Type": "application/json",
                    "Accept": "image/jpeg",
                },
                json={
                    "prompt": prompt,
                    "width": 1344,
                    "height": 768,
                    "steps": 28,
                    "cfg_scale": 3.5,
                },
            )
            resp.raise_for_status()
            img_bytes = resp.content
            if len(img_bytes) > 5000:
                logger.info(f"[CoverImage] Fireworks Flux Dev: {len(img_bytes)} bytes")
                return img_bytes
            logger.warning(f"[CoverImage] Fireworks response too small: {len(img_bytes)} bytes")
        except httpx.HTTPError as exc:
            logger.debug(f"[CoverImage] Fireworks HTTP error: {exc}")
        except Exception as exc:
            logger.warning(f"[CoverImage] Fireworks unexpected error: {exc}", exc_info=True)
        return None

    async def _pollinations(self, prompt: str) -> bytes | None:
        """Fallback: Pollinations.ai free image generation."""
        import time

        encoded_prompt = urllib.parse.quote(prompt)
        seed = int(time.time()) % 99999
        client = self._get_client()

        for model in ["sana", "turbo"]:
            try:
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                    f"?width=1200&height=630&seed={seed}&nologo=true&model={model}"
                )
                resp = await client.get(url, headers={"User-Agent": "BaliZero/1.0"})
                if resp.status_code == 200 and len(resp.content) > 5000:
                    logger.info(f"[CoverImage] Pollinations [{model}]: {len(resp.content)} bytes")
                    return resp.content
            except httpx.HTTPError as exc:
                logger.debug(f"[CoverImage] Pollinations [{model}] HTTP error: {exc}")
            except Exception as exc:
                logger.warning(
                    f"[CoverImage] Pollinations [{model}] unexpected error: {exc}",
                    exc_info=True,
                )
        return None

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    @staticmethod
    async def _save_to_db(*, article_id: str, image_url: str, pool: Any) -> None:
        """Persist generated image_url to news_items table."""
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE news_items SET image_url = $1 WHERE id = $2 AND image_url IS NULL",
                image_url,
                article_id,
            )


# Module-level singleton
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
    slug: str | None = None,
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
        slug=slug,
        pool=pool,
    )
