"""Vector store service — Qdrant client wrapper.

Provides text-based and embedding-based search over Qdrant collections.
All endpoints read from Settings (no hardcoded URLs).
"""

from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, ScoredPoint

from nuzantara_graph.config import Settings
from nuzantara_graph.services.collection_registry import (
    DEFAULT_COLLECTION,
    resolve_collection_name,
)
from nuzantara_schemas.state import RetrievedDocument

logger = structlog.get_logger()

class VectorStore:
    """Qdrant vector search with embedding-based and text-based retrieval.

    Usage:
        store = VectorStore.from_settings(settings, embeddings=emb_svc)
        docs = await store.search_by_text("PT PMA requirements", top_k=10)
    """

    def __init__(
        self,
        qdrant_url: str = "",
        qdrant_api_key: str = "",
        embeddings: Any | None = None,
    ) -> None:
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self._embeddings = embeddings
        self._client: AsyncQdrantClient | None = None

    @classmethod
    def from_settings(cls, settings: Settings, embeddings: Any | None = None) -> VectorStore:
        return cls(
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            embeddings=embeddings,
        )

    async def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key or None,
                timeout=30,
            )
        return self._client

    @property
    def client(self) -> AsyncQdrantClient:
        """Synchronous accessor for the underlying qdrant client.

        Lazily initializes on first access. This property exists because
        ``main.py`` and ``api/routes.py`` pass ``services.vector_store.client``
        directly to the semantic cache, which needs the concrete qdrant
        client rather than an async accessor.
        """
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key or None,
                timeout=30,
            )
        return self._client

    async def search(
        self,
        query_embedding: list[float],
        collection: str = DEFAULT_COLLECTION,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedDocument]:
        """Search for similar documents by pre-computed embedding vector."""
        client = await self._get_client()

        qdrant_filter = _build_filter(filters) if filters else None
        resolved_collection = resolve_collection_name(collection)

        results: list[ScoredPoint] = await client.search(
            collection_name=resolved_collection,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        return [_point_to_doc(point) for point in results]

    async def search_by_text(
        self,
        query: str,
        collection: str = DEFAULT_COLLECTION,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedDocument]:
        """Search by text — embeds the query, then searches by vector."""
        if self._embeddings is None:
            raise RuntimeError(
                "EmbeddingsService not configured. "
                "Pass embeddings= to VectorStore constructor or use from_settings()."
            )

        embedding = await self._embeddings.embed_text(query)
        return await self.search(
            query_embedding=embedding,
            collection=collection,
            top_k=top_k,
            filters=filters,
        )

    async def health_check(self) -> dict[str, Any]:
        """Verify Qdrant is reachable and report collection stats."""
        try:
            client = await self._get_client()
            collections = await client.get_collections()
            collection_names = [c.name for c in collections.collections]
            return {
                "status": "healthy",
                "url": self.qdrant_url,
                "collections": collection_names,
                "collection_count": len(collection_names),
                "ok": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self.qdrant_url,
                "error": str(e),
                "ok": False,
            }

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None


def _point_to_doc(point: ScoredPoint) -> RetrievedDocument:
    """Convert a Qdrant ScoredPoint to our RetrievedDocument model."""
    payload = point.payload or {}
    return RetrievedDocument(
        id=str(point.id),
        content=payload.get("content", ""),
        score=point.score,
        metadata={k: v for k, v in payload.items() if k != "content"},
    )


def _build_filter(filters: dict[str, Any]) -> Filter:
    """Build a Qdrant Filter from a simple key-value dict."""
    conditions = []
    for key, value in filters.items():
        conditions.append(
            FieldCondition(key=key, match=MatchValue(value=value))
        )
    return Filter(must=conditions)
