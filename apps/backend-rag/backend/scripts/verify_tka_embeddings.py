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
            except Exception as e:
                print(f"❌ Search failed: {e}")
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
            except Exception as e:
                print(f"❌ Scroll failed: {e}")
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
    score = result.get("score", 0)

    print(f"\n{'=' * 60}")
    print(f"Result #{index + 1} (Score: {score:.4f})")
    print(f"{'=' * 60}")
    print(f"KBLI Code: {payload.get('kbli_code', 'N/A')}")
    print(f"Title: {payload.get('kbli_title', 'N/A')}")
    print(
        f"Category: {payload.get('category_name', 'N/A')} (ID: {payload.get('category_id', 'N/A')})",
    )
    print(f"Total Positions: {payload.get('total_positions', 0)}")
    print(f"Selected Positions: {payload.get('selected_positions', 0)}")
    print(f"ISCO Groups: {', '.join(payload.get('isco_groups', []))}")

    positions = payload.get("positions", [])
    if positions:
        print(f"\nTop Positions ({min(5, len(positions))} of {len(positions)}):")
        for i, pos in enumerate(positions[:5]):
            print(
                f"  {i + 1}. {pos.get('title_en', 'N/A')} ({pos.get('title_id', 'N/A')}) - ISCO {pos.get('isco', 'N/A')}",
            )


async def main():
    """Main verification function."""
    # Parse arguments
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    # Initialize clients
    try:
        embedder = OpenAIEmbedder()
        qdrant = QdrantClient()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    print(f"🔗 Qdrant URL: {qdrant.url}")
    print(f"📦 Collection: {COLLECTION_NAME}")
    print()

    # Step 1: Check collection stats
    print("=" * 60)
    print("COLLECTION STATISTICS")
    print("=" * 60)

    stats = await qdrant.get_stats(COLLECTION_NAME)
    if not stats.get("exists"):
        print(f"❌ Collection '{COLLECTION_NAME}' does not exist or is not accessible")
        print(f"Error: {stats.get('error', 'Unknown error')}")
        sys.exit(1)

    print("✅ Collection exists")
    print(f"📊 Points count: {stats['points_count']}")
    print(f"📊 Vector size: {stats['vector_size']}")
    print(f"📊 Distance metric: {stats['distance']}")
    print(f"📊 Status: {stats['status']}")

    # Step 2: Sample some points
    print("\n" + "=" * 60)
    print("SAMPLE POINTS")
    print("=" * 60)

    points, _ = await qdrant.scroll(COLLECTION_NAME, limit=3)
    if points:
        print(f"✅ Found {len(points)} sample points:")
        for i, point in enumerate(points):
            payload = point.get("payload", {})
            print(f"\n  Point {i + 1}:")
            print(f"    ID: {point.get('id', 'N/A')}")
            print(
                f"    KBLI: {payload.get('kbli_code', 'N/A')} - {payload.get('kbli_title', 'N/A')}",
            )
            print(f"    Positions count: {len(payload.get('positions', []))}")
    else:
        print("⚠️ No points found in collection")

    # Step 3: Semantic search (if query provided)
    if query:
        print("\n" + "=" * 60)
        print(f"SEMANTIC SEARCH: '{query}'")
        print("=" * 60)

        print("Generating query embedding...")
        query_vector = await embedder.generate_embedding(query)

        print("Searching collection...")
        results = await qdrant.search(COLLECTION_NAME, query_vector, limit=5)

        if results:
            print(f"✅ Found {len(results)} results:")
            for i, result in enumerate(results):
                print_result(result, i)
        else:
            print("⚠️ No results found")
    else:
        print("\n" + "=" * 60)
        print("SEMANTIC SEARCH")
        print("=" * 60)
        print("No query provided. To test semantic search, run:")
        print(f"  python {sys.argv[0]} 'your search query'")
        print("\nExample queries:")
        print("  - 'food production manager'")
        print("  - 'IT manager software'")
        print("  - 'engineer mechanical'")
        print("  - 'quality control manager'")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
