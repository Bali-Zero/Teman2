"""Embeddings service — text-embedding-3-small (1536 dims).

FROZEN model — never change the model or dimensions.
Uses the OpenAI client directly for embedding generation.
"""

from __future__ import annotations

from typing import Any

import structlog
from openai import AsyncOpenAI

from nuzantara_graph.config import Settings

logger = structlog.get_logger()

# FROZEN — never change
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


class EmbeddingsService:
    """OpenAI embeddings client for text-embedding-3-small.

    Usage:
        svc = EmbeddingsService.from_settings(settings)
        vector = await svc.embed_text("Hello world")
        vectors = await svc.embed_batch(["Hello", "World"])
    """

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = EMBEDDING_MODEL
        self.dimensions = EMBEDDING_DIMS

    @classmethod
    def from_settings(cls, settings: Settings) -> EmbeddingsService:
        if not settings.openai_api_key:
            raise ValueError("NUZANTARA_OPENAI_API_KEY is required for embeddings")
        return cls(api_key=settings.openai_api_key)

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns 1536-dim vector."""
        response = await self._client.embeddings.create(
            input=text,
            model=self.model,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call.

        OpenAI supports up to 2048 texts per batch request.
        """
        if not texts:
            return []

        response = await self._client.embeddings.create(
            input=texts,
            model=self.model,
        )
        return [item.embedding for item in response.data]

    async def health_check(self) -> dict[str, Any]:
        """Verify the embeddings service is reachable and model is correct."""
        try:
            vec = await self.embed_text("health check")
            return {
                "status": "healthy",
                "model": self.model,
                "dimensions": len(vec),
                "expected_dimensions": self.dimensions,
                "ok": len(vec) == self.dimensions,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "model": self.model,
                "error": str(e),
                "ok": False,
            }
