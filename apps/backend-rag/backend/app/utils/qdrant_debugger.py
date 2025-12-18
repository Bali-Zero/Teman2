"""
Qdrant Debugger
Extended debugger for Qdrant collections with health analysis and query performance
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CollectionHealth:
    """Health status of a Qdrant collection"""

    name: str
    points_count: int
    vectors_count: int
    indexed: bool
    status: str
    config: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class QueryPerformance:
    """Performance metrics for a Qdrant query"""

    collection: str
    query: str
    duration_ms: float
    results_count: int
    vector_dimension: int | None = None
    error: str | None = None


class QdrantDebugger:
    """
    Debugger for Qdrant operations.

    Extends the existing debug_qdrant.py script with programmatic access.
    """

    def __init__(self, qdrant_url: str | None = None, api_key: str | None = None):
        """
        Initialize Qdrant debugger.

        Args:
            qdrant_url: Qdrant URL (defaults to settings.qdrant_url)
            api_key: Qdrant API key (defaults to settings.qdrant_api_key)
        """
        self.qdrant_url = qdrant_url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.headers = {}
        if self.api_key:
            self.headers["api-key"] = self.api_key

    async def get_collection_health(self, collection_name: str) -> CollectionHealth:
        """
        Get health status of a collection.

        Args:
            collection_name: Collection name

        Returns:
            CollectionHealth object
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.qdrant_url, headers=self.headers, timeout=10.0
            ) as client:
                # Get collection info
                response = await client.get(f"/collections/{collection_name}")
                response.raise_for_status()
                data = response.json().get("result", {})

                return CollectionHealth(
                    name=collection_name,
                    points_count=data.get("points_count", 0),
                    vectors_count=data.get("vectors_count", 0),
                    indexed=data.get("config", {}).get("params", {}).get("vectors", {}).get(
                        "on_disk", False
                    ),
                    status=data.get("status", "unknown"),
                    config=data.get("config", {}),
                )
        except Exception as e:
            logger.error(f"Failed to get collection health for {collection_name}: {e}")
            return CollectionHealth(
                name=collection_name,
                points_count=0,
                vectors_count=0,
                indexed=False,
                status="error",
                error=str(e),
            )

    async def get_all_collections_health(self) -> list[CollectionHealth]:
        """
        Get health status of all collections.

        Returns:
            List of CollectionHealth objects
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.qdrant_url, headers=self.headers, timeout=10.0
            ) as client:
                # Get all collections
                response = await client.get("/collections")
                response.raise_for_status()
                collections = response.json().get("result", {}).get("collections", [])

                # Get health for each collection
                health_statuses = []
                for coll in collections:
                    coll_name = coll.get("name")
                    if coll_name:
                        health = await self.get_collection_health(coll_name)
                        health_statuses.append(health)

                return health_statuses
        except Exception as e:
            logger.error(f"Failed to get all collections health: {e}")
            return []

    async def analyze_query_performance(
        self, collection: str, query_vector: list[float], limit: int = 10
    ) -> QueryPerformance:
        """
        Analyze query performance.

        Args:
            collection: Collection name
            query_vector: Query vector
            limit: Number of results to retrieve

        Returns:
            QueryPerformance object
        """
        import time

        start_time = time.time()

        try:
            async with httpx.AsyncClient(
                base_url=self.qdrant_url, headers=self.headers, timeout=30.0
            ) as client:
                # Perform search
                search_payload = {
                    "vector": query_vector,
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                }

                response = await client.post(
                    f"/collections/{collection}/points/search", json=search_payload
                )
                response.raise_for_status()

                duration_ms = (time.time() - start_time) * 1000
                results = response.json().get("result", [])

                return QueryPerformance(
                    collection=collection,
                    query=f"vector_search_{len(query_vector)}d",
                    duration_ms=duration_ms,
                    results_count=len(results),
                    vector_dimension=len(query_vector),
                )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query performance analysis failed: {e}")
            return QueryPerformance(
                collection=collection,
                query=f"vector_search_{len(query_vector)}d",
                duration_ms=duration_ms,
                results_count=0,
                error=str(e),
            )

    async def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """
        Get detailed statistics for a collection.

        Args:
            collection_name: Collection name

        Returns:
            Collection statistics
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.qdrant_url, headers=self.headers, timeout=10.0
            ) as client:
                # Get collection info
                response = await client.get(f"/collections/{collection_name}")
                response.raise_for_status()
                data = response.json().get("result", {})

                return {
                    "name": collection_name,
                    "points_count": data.get("points_count", 0),
                    "vectors_count": data.get("vectors_count", 0),
                    "status": data.get("status", "unknown"),
                    "config": data.get("config", {}),
                }
        except Exception as e:
            logger.error(f"Failed to get collection stats for {collection_name}: {e}")
            return {
                "name": collection_name,
                "error": str(e),
            }

    async def inspect_document(
        self, collection: str, document_id: str | int
    ) -> dict[str, Any] | None:
        """
        Inspect a specific document in a collection.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            Document data or None if not found
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.qdrant_url, headers=self.headers, timeout=10.0
            ) as client:
                response = await client.post(
                    f"/collections/{collection}/points/retrieve",
                    json={"ids": [document_id], "with_payload": True, "with_vector": False},
                )
                response.raise_for_status()

                results = response.json().get("result", [])
                if results:
                    return results[0]
                return None
        except Exception as e:
            logger.error(f"Failed to inspect document {document_id} in {collection}: {e}")
            return None

