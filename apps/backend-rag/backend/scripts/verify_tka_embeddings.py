#!/usr/bin/env python3
"""
TKA Embeddings Verification Script
Tests semantic search on the kbli_tka collection.

Usage:
    python verify_tka_embeddings.py [query]

Examples:
    python verify_tka_embeddings.py "food production manager"
    python verify_tka_embeddings.py "IT manager software"
    python verify_tka_embeddings.py "engineer mechanical"
"""

import asyncio
import os
import sys
from typing import Any

import httpx

DEFAULT_QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kbli_tka"


class OpenAIEmbedder:
    """OpenAI embedding generator."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.model = "text-embedding-3-small"

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.embeddings.create(model=self.model, input=[text])
        return response.data[0].embedding


class QdrantClient:
    """Simple Qdrant client for search."""

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.url = (url or os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL).rstrip("/")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.timeout = 30.0

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    async def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors."""
        async with httpx.AsyncClient() as client:
            url = f"{self.url}/collections/{collection_name}/points/search"
            payload = {
                "vector": vector,
                "limit": limit,
                "with_payload": True,
            }

            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
            except Exception:
                return []

    async def scroll(
        self,
        collection_name: str,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], int]:
        """Scroll through points in collection."""
        async with httpx.AsyncClient() as client:
            url = f"{self.url}/collections/{collection_name}/points/scroll"
            payload = {
                "limit": limit,
                "with_payload": True,
            }

            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                result = data.get("result", {})
                return result.get("points", []), result.get("next_page_offset")
            except Exception:
                return [], 0

    async def get_stats(self, collection_name: str) -> dict[str, Any]:
        """Get collection statistics."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.url}/collections/{collection_name}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json().get("result", {})
                return {
                    "exists": True,
                    "points_count": data.get("points_count", 0),
                    "vector_size": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size", 0),
                    "distance": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("distance", "Unknown"),
                    "status": data.get("status", "unknown"),
                }
            except Exception as e:
                return {"exists": False, "error": str(e)}


def print_result(result: dict[str, Any], index: int):
    """Print a search result."""
    payload = result.get("payload", {})
    result.get("score", 0)


    positions = payload.get("positions", [])
    if positions:
        for _i, _pos in enumerate(positions[:5]):
            pass


async def main():
    """Main verification function."""
    # Parse arguments
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    # Initialize clients
    try:
        embedder = OpenAIEmbedder()
        qdrant = QdrantClient()
    except ValueError:
        sys.exit(1)


    # Step 1: Check collection stats

    stats = await qdrant.get_stats(COLLECTION_NAME)
    if not stats.get("exists"):
        sys.exit(1)


    # Step 2: Sample some points

    points, _ = await qdrant.scroll(COLLECTION_NAME, limit=3)
    if points:
        for i, point in enumerate(points):
            point.get("payload", {})
    else:
        pass

    # Step 3: Semantic search (if query provided)
    if query:

        query_vector = await embedder.generate_embedding(query)

        results = await qdrant.search(COLLECTION_NAME, query_vector, limit=5)

        if results:
            for i, result in enumerate(results):
                print_result(result, i)
        else:
            pass
    else:
        pass



if __name__ == "__main__":
    asyncio.run(main())
