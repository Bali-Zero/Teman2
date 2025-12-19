"""
ZANTARA RAG - Vector Database (Qdrant)
Async Qdrant client wrapper for embeddings storage and retrieval

Uses httpx for async HTTP requests with connection pooling.
All operations are async to avoid blocking the event loop.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

try:
    from app.core.config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)

# Constants
DEFAULT_OPENAI_DIMENSIONS = 1536
DEFAULT_SENTENCE_TRANSFORMERS_DIMENSIONS = 384
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

# Connection pool limits
MAX_KEEPALIVE_CONNECTIONS = 10
MAX_CONNECTIONS = 20
CONNECT_TIMEOUT = 10.0  # seconds

# Metrics tracking
_qdrant_metrics = {
    "search_calls": 0,
    "search_total_time": 0.0,
    "upsert_calls": 0,
    "upsert_total_time": 0.0,
    "upsert_documents_total": 0,
    "retry_count": 0,
    "errors": 0,
}


def get_qdrant_metrics() -> dict[str, Any]:
    """
    Get Qdrant operation metrics for monitoring.

    Returns:
        Dictionary with operation metrics including averages
    """
    metrics = _qdrant_metrics.copy()
    if metrics["search_calls"] > 0:
        metrics["search_avg_time_ms"] = (
            metrics["search_total_time"] / metrics["search_calls"]
        ) * 1000
    else:
        metrics["search_avg_time_ms"] = 0.0

    if metrics["upsert_calls"] > 0:
        metrics["upsert_avg_time_ms"] = (
            metrics["upsert_total_time"] / metrics["upsert_calls"]
        ) * 1000
        metrics["upsert_avg_docs_per_call"] = (
            metrics["upsert_documents_total"] / metrics["upsert_calls"]
        )
    else:
        metrics["upsert_avg_time_ms"] = 0.0
        metrics["upsert_avg_docs_per_call"] = 0.0

    return metrics


async def _retry_with_backoff(
    func, max_retries: int = MAX_RETRIES, base_delay: float = RETRY_BASE_DELAY
):
    """
    Retry function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Function result

    Raises:
        Exception: If all retries fail
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} after {delay}s: {str(e)[:100]}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} retry attempts failed")
                raise last_exception
    raise last_exception


class QdrantClient:
    """
    Async Qdrant vector database client with connection pooling.

    Uses httpx.AsyncClient with connection pooling for efficient async operations.
    All methods are async to avoid blocking the event loop.

    Usage:
        async with QdrantClient(url="http://localhost:6333") as client:
            results = await client.search(embedding, limit=10)

    Or without context manager:
        client = QdrantClient(url="http://localhost:6333")
        results = await client.search(embedding, limit=10)
        await client.close()  # Clean up connections
    """

    def __init__(
        self,
        qdrant_url: str | None = None,
        collection_name: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize Qdrant client.

        Args:
            qdrant_url: Qdrant server URL (default from env/settings)
            collection_name: Name of collection to use
            api_key: Qdrant API key for authentication (default from settings)
            timeout: Request timeout in seconds (default from settings or 30)
        """
        # Get Qdrant URL from settings
        self.qdrant_url = qdrant_url or (
            settings.qdrant_url if settings else "http://localhost:6333"
        )
        self.collection_name = collection_name or "knowledge_base"

        # Get API key from settings or parameter
        self.api_key = api_key or (settings.qdrant_api_key if settings else None)

        # Get timeout from settings or parameter (default 30s)
        self.timeout = (
            timeout or (getattr(settings, "qdrant_timeout", None) if settings else None) or 30.0
        )

        # Remove trailing slash
        self.qdrant_url = self.qdrant_url.rstrip("/")

        # Initialize HTTP client (lazy initialization with connection pooling)
        self._http_client: httpx.AsyncClient | None = None

        logger.info(
            f"Qdrant client initialized: collection='{self.collection_name}', "
            f"url='{self.qdrant_url}', api_key_configured={bool(self.api_key)}, "
            f"timeout={self.timeout}s"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create async HTTP client with connection pooling.

        Returns:
            httpx.AsyncClient instance with connection pool configured
        """
        if self._http_client is None:
            # Create async client with connection pooling
            self._http_client = httpx.AsyncClient(
                base_url=self.qdrant_url,
                headers=self._get_headers(),
                timeout=httpx.Timeout(
                    self.timeout,
                    connect=CONNECT_TIMEOUT,
                ),
                limits=httpx.Limits(
                    max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
                    max_connections=MAX_CONNECTIONS,
                ),
                http2=True,  # HTTP/2 support for better performance
            )
            logger.debug(f"✅ Created Qdrant HTTP client with connection pool: {self.qdrant_url}")
        return self._http_client

    async def close(self):
        """
        Close HTTP client and connection pool.

        Should be called when done with the client to free resources.
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            logger.debug("✅ Closed Qdrant HTTP client")

    async def __aenter__(self):
        """
        Async context manager entry.

        Returns:
            Self for use in async with statement
        """
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.

        Automatically closes HTTP client when exiting context.
        """
        await self.close()

    def _get_headers(self) -> dict[str, str]:
        """
        Get headers for API requests including API key if configured.

        Returns:
            Dictionary with headers including API key if available
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def _convert_filter_to_qdrant_format(
        self, filter_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Convert simplified filter format to Qdrant filter format.

        Supports:
        - {"tier": {"$in": ["S", "A"]}} -> must match any of these values
        - {"status_vigensi": {"$ne": "dicabut"}} -> must_not match this value
        - {"status_vigensi": "berlaku"} -> must match this value

        Args:
            filter_dict: Simplified filter dictionary

        Returns:
            Qdrant filter format or None if filter is empty/invalid
        """
        if not filter_dict:
            return None

        must_conditions = []
        must_not_conditions = []

        for key, value in filter_dict.items():
            if isinstance(value, dict):
                # Handle operators like $in, $ne, etc.
                if "$in" in value:
                    # Match any of the values
                    match_values = value["$in"]
                    if match_values:
                        must_conditions.append(
                            {"key": f"metadata.{key}", "match": {"any": match_values}}
                        )
                elif "$ne" in value:
                    # Must NOT match this value
                    must_not_conditions.append(
                        {"key": f"metadata.{key}", "match": {"value": value["$ne"]}}
                    )
                elif "$nin" in value:
                    # Must NOT match any of these values
                    for excluded_value in value["$nin"]:
                        must_not_conditions.append(
                            {"key": f"metadata.{key}", "match": {"value": excluded_value}}
                        )
            else:
                # Direct value match
                must_conditions.append({"key": f"metadata.{key}", "match": {"value": value}})

        result = {}
        if must_conditions:
            result["must"] = must_conditions
        if must_not_conditions:
            result["must_not"] = must_not_conditions

        return result if result else None

    async def search(
        self, query_embedding: list[float], filter: dict[str, Any] | None = None, limit: int = 5,
        vector_name: str | None = None
    ) -> dict[str, Any]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            filter: Metadata filter (simplified format, converted to Qdrant format)
            limit: Maximum number of results
            vector_name: Named vector to use (e.g., "dense" for hybrid collections)

        Returns:
            Dictionary with search results (compatible with Qdrant format)
        """
        # Validate input
        if not query_embedding:
            raise ValueError("query_embedding cannot be empty")
        if not isinstance(query_embedding[0], (int, float)):
            raise TypeError("query_embedding must be list of numbers")

        async def _do_search():
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points/search"

            # Use named vector if specified, otherwise use default format
            if vector_name:
                payload = {
                    "vector": {"name": vector_name, "vector": query_embedding},
                    "limit": limit,
                    "with_payload": True
                }
            else:
                payload = {"vector": query_embedding, "limit": limit, "with_payload": True}

            # Add filter if provided (Qdrant filter format)
            if filter:
                qdrant_filter = self._convert_filter_to_qdrant_format(filter)
                if qdrant_filter:
                    payload["filter"] = qdrant_filter

            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                results = data.get("result", [])

                # Transform Qdrant results to Qdrant-compatible format
                formatted_results = {
                    "ids": [str(r["id"]) for r in results],
                    "documents": [r["payload"].get("text", "") for r in results],
                    "metadatas": [r["payload"].get("metadata", {}) for r in results],
                    "distances": [
                        1.0 - r["score"] for r in results
                    ],  # Convert similarity to distance
                    "total_found": len(results),
                }

                logger.debug(
                    f"Qdrant search: collection={self.collection_name}, found {len(results)} results"
                )
                return formatted_results

            except httpx.TimeoutException as e:
                logger.error(f"Qdrant search timeout: {e}")
                raise TimeoutError(f"Qdrant request timeout after {self.timeout}s")
            except httpx.HTTPStatusError as e:
                error_text = e.response.text if hasattr(e.response, "text") else str(e.response)
                # Raise exception for 5xx errors (transient) to trigger retry
                if 500 <= e.response.status_code < 600:
                    raise Exception(f"Qdrant server error {e.response.status_code}: {error_text}")
                # Auto-retry with named vector if collection uses named vectors
                if e.response.status_code == 400 and "Vector params for" in error_text and not vector_name:
                    logger.info("Collection uses named vectors, retrying with 'dense'")
                    # Retry with named vector
                    payload["vector"] = {"name": "dense", "vector": query_embedding}
                    try:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                        data = response.json()
                        results = data.get("result", [])
                        return {
                            "ids": [str(r["id"]) for r in results],
                            "documents": [r["payload"].get("text", "") for r in results],
                            "metadatas": [r["payload"].get("metadata", {}) for r in results],
                            "distances": [1.0 - r["score"] for r in results],
                            "total_found": len(results),
                        }
                    except Exception as retry_err:
                        logger.error(f"Retry with named vector failed: {retry_err}")
                # For 4xx errors (client errors), return empty results
                logger.error(f"Qdrant search failed: {e.response.status_code} - {error_text}")
                return {
                    "ids": [],
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                    "total_found": 0,
                }
            except httpx.RequestError as e:
                logger.error(f"Qdrant request error: {e}")
                raise ConnectionError(f"Qdrant connection error: {e}")

        start_time = time.time()
        try:
            result = await _retry_with_backoff(_do_search)
            # Track metrics
            elapsed = time.time() - start_time
            _qdrant_metrics["search_calls"] += 1
            _qdrant_metrics["search_total_time"] += elapsed
            logger.debug(f"Qdrant search completed in {elapsed * 1000:.2f}ms")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            _qdrant_metrics["errors"] += 1
            logger.error(f"Qdrant search error after retries: {e}", exc_info=True)
            return {"ids": [], "documents": [], "metadatas": [], "distances": [], "total_found": 0}

    async def get_collection_stats(self) -> dict[str, Any]:
        """
        Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}"

            try:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json().get("result", {})
                points_count = data.get("points_count", 0)

                return {
                    "collection_name": self.collection_name,
                    "total_documents": points_count,
                    "vector_size": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size", DEFAULT_OPENAI_DIMENSIONS),
                    "distance": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("distance", "Cosine"),
                    "status": data.get("status", "unknown"),
                }
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to get collection stats: {e.response.status_code}")
                return {
                    "collection_name": self.collection_name,
                    "error": f"HTTP {e.response.status_code}",
                }
            except httpx.RequestError as e:
                logger.error(f"Qdrant request error getting stats: {e}")
                return {"collection_name": self.collection_name, "error": str(e)}

        except Exception as e:
            logger.error(f"Error getting Qdrant stats: {e}")
            return {"collection_name": self.collection_name, "error": str(e)}

    async def create_collection(
        self,
        vector_size: int = DEFAULT_OPENAI_DIMENSIONS,
        distance: str = "Cosine",
        on_disk_payload: bool | None = None,
        enable_sparse: bool = False,
    ) -> bool:
        """
        Create a new collection with optional sparse vector support.

        Args:
            vector_size: Size of the dense vectors (default 1536 for OpenAI)
            distance: Distance metric (Cosine, Euclidean, Dot)
            on_disk_payload: Whether to store payload on disk (optional)
            enable_sparse: Enable BM25 sparse vector support for hybrid search

        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}"

            # Use named vectors for hybrid search compatibility
            if enable_sparse:
                payload = {
                    "vectors": {
                        "dense": {"size": vector_size, "distance": distance}
                    },
                    "sparse_vectors": {
                        "bm25": {"index": {"on_disk": False}}
                    }
                }
                logger.info(f"Creating collection with sparse vector support (BM25)")
            else:
                payload = {"vectors": {"size": vector_size, "distance": distance}}

            if on_disk_payload is not None:
                payload["on_disk_payload"] = on_disk_payload

            try:
                response = await client.put(url, json=payload)
                response.raise_for_status()

                logger.info(f"Created collection '{self.collection_name}'")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Failed to create collection: {e.response.status_code} - {e.response.text}"
                )
                return False
            except httpx.RequestError as e:
                logger.error(f"Qdrant request error creating collection: {e}")
                return False

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return False

    async def upsert_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
        batch_size: int = 500,
    ) -> dict[str, Any]:
        """
        Insert or update documents in the collection.
        Automatically batches large uploads to avoid timeout/memory issues.

        Args:
            chunks: List of text chunks
            embeddings: List of embedding vectors
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs (auto-generated if not provided)
            batch_size: Number of documents per batch (default: 500)

        Returns:
            Dictionary with operation results

        Raises:
            ValueError: If input lengths don't match
            Exception: If upsert fails after retries
        """
        start_time = time.time()
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points"

            # Generate IDs if not provided
            if not ids:
                import uuid

                ids = [str(uuid.uuid4()) for _ in range(len(chunks))]

            # Validate input lengths
            if not (len(chunks) == len(embeddings) == len(metadatas) == len(ids)):
                raise ValueError("chunks, embeddings, metadatas, and ids must have same length")

            # Batch processing for large uploads
            total = len(chunks)
            total_added = 0
            errors = []

            for i in range(0, total, batch_size):
                batch_chunks = chunks[i : i + batch_size]
                batch_embeddings = embeddings[i : i + batch_size]
                batch_metadatas = metadatas[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]

                # Build points array for this batch
                points = []
                for j in range(len(batch_chunks)):
                    point = {
                        "id": batch_ids[j],
                        "vector": batch_embeddings[j],
                        "payload": {"text": batch_chunks[j], "metadata": batch_metadatas[j]},
                    }
                    points.append(point)

                # Upsert batch via REST API
                payload = {"points": points}
                try:
                    response = await client.put(url, json=payload, params={"wait": "true"})
                    response.raise_for_status()

                    total_added += len(batch_chunks)
                    logger.info(
                        f"Upserted batch {i // batch_size + 1}: {len(batch_chunks)}/{total} documents "
                        f"to Qdrant collection '{self.collection_name}'"
                    )
                except httpx.HTTPStatusError as e:
                    error_msg = f"HTTP {e.response.status_code}"
                    if hasattr(e.response, "text"):
                        error_msg += f": {e.response.text}"
                    errors.append(error_msg)
                    logger.error(f"Qdrant upsert batch failed: {error_msg}")
                except httpx.RequestError as e:
                    error_msg = f"Request error: {e}"
                    errors.append(error_msg)
                    logger.error(f"Qdrant upsert batch request error: {error_msg}")

            if errors:
                return {
                    "success": False,
                    "error": f"Some batches failed: {errors}",
                    "documents_added": total_added,
                    "collection": self.collection_name,
                }

            logger.info(
                f"Successfully upserted {total_added} documents to Qdrant collection '{self.collection_name}'"
            )
            # Track metrics
            elapsed = time.time() - start_time
            _qdrant_metrics["upsert_calls"] += 1
            _qdrant_metrics["upsert_total_time"] += elapsed
            _qdrant_metrics["upsert_documents_total"] += total_added
            logger.debug(f"Qdrant upsert completed in {elapsed * 1000:.2f}ms ({total_added} docs)")
            return {
                "success": True,
                "documents_added": total_added,
                "collection": self.collection_name,
            }

        except Exception as e:
            logger.error(f"Error upserting to Qdrant: {e}", exc_info=True)
            raise

    @property
    def collection(self):
        """
        Property to provide Qdrant-compatible collection interface.
        Returns self for direct method access.
        """
        return self

    async def get(self, ids: list[str], include: list[str] | None = None) -> dict[str, Any]:
        """
        Retrieve points by IDs (Qdrant-compatible interface).

        Args:
            ids: List of point IDs to retrieve
            include: List of fields to include (e.g., ["embeddings", "payload"])

        Returns:
            Dictionary with Qdrant-compatible format
        """
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points"

            # Qdrant retrieve endpoint
            payload = {"ids": ids}
            if include:
                # Map Qdrant include to Qdrant with_payload/with_vectors
                with_payload = "payload" in include or "metadatas" in include
                with_vectors = "embeddings" in include
                params = {}
                if with_payload:
                    params["with_payload"] = True
                if with_vectors:
                    params["with_vectors"] = True
            else:
                params = {"with_payload": True, "with_vectors": True}

            try:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

                results = response.json().get("result", [])

                # Transform to Qdrant format
                formatted = {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

                for point in results:
                    formatted["ids"].append(str(point["id"]))
                    if "vector" in point:
                        formatted["embeddings"].append(point["vector"])
                    else:
                        formatted["embeddings"].append(None)

                    payload_data = point.get("payload", {})
                    formatted["documents"].append(payload_data.get("text", ""))
                    formatted["metadatas"].append(payload_data.get("metadata", {}))

                return formatted
            except httpx.HTTPStatusError as e:
                logger.error(f"Qdrant get failed: {e.response.status_code} - {e.response.text}")
                return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
            except httpx.RequestError as e:
                logger.error(f"Qdrant get request error: {e}")
                return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

        except Exception as e:
            logger.error(f"Qdrant get error: {e}")
            return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

    async def delete(self, ids: list[str]) -> dict[str, Any]:
        """
        Delete points by IDs (Qdrant-compatible interface).

        Args:
            ids: List of point IDs to delete

        Returns:
            Dictionary with operation results

        Raises:
            Exception: If delete fails
        """
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points/delete"

            payload = {"points": ids}
            try:
                response = await client.post(url, json=payload, params={"wait": "true"})
                response.raise_for_status()

                logger.info(
                    f"Deleted {len(ids)} points from Qdrant collection '{self.collection_name}'"
                )
                return {"success": True, "deleted_count": len(ids)}
            except httpx.HTTPStatusError as e:
                logger.error(f"Qdrant delete failed: {e.response.status_code} - {e.response.text}")
                return {"success": False, "error": f"HTTP {e.response.status_code}"}
            except httpx.RequestError as e:
                logger.error(f"Qdrant delete request error: {e}")
                raise ConnectionError(f"Qdrant connection error: {e}")

        except Exception as e:
            logger.error(f"Error deleting from Qdrant: {e}")
            raise

    async def peek(self, limit: int = 10) -> dict[str, Any]:
        """
        Peek at points in the collection (Qdrant-compatible interface).

        Args:
            limit: Maximum number of points to return

        Returns:
            Dictionary with sample points in Qdrant format
        """
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points/scroll"

            payload = {"limit": limit, "with_payload": True, "with_vectors": False}
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json().get("result", {})
                points = data.get("points", [])

                # Transform to Qdrant format
                formatted = {
                    "ids": [str(p["id"]) for p in points],
                    "documents": [p.get("payload", {}).get("text", "") for p in points],
                    "metadatas": [p.get("payload", {}).get("metadata", {}) for p in points],
                }

                return formatted
            except httpx.HTTPStatusError as e:
                logger.error(f"Qdrant peek failed: {e.response.status_code}")
                return {"ids": [], "documents": [], "metadatas": []}
            except httpx.RequestError as e:
                logger.error(f"Qdrant peek request error: {e}")
                return {"ids": [], "documents": [], "metadatas": []}

        except Exception as e:
            logger.error(f"Error peeking Qdrant collection: {e}")
            return {"ids": [], "documents": [], "metadatas": []}

    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_sparse: dict[str, Any] | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 5,
        prefetch_limit: int = 20,
    ) -> dict[str, Any]:
        """
        Hybrid search combining dense and sparse (BM25) vectors with RRF fusion.

        Uses Qdrant's prefetch + fusion API for optimal hybrid search.

        Args:
            query_embedding: Dense query embedding vector (1536 dims)
            query_sparse: Sparse query vector {"indices": [...], "values": [...]}
            filter: Metadata filter (simplified format)
            limit: Maximum number of final results
            prefetch_limit: Number of candidates to prefetch from each vector type

        Returns:
            Dictionary with search results in standard format
        """
        # If no sparse vector provided, fall back to dense-only search
        if not query_sparse or not query_sparse.get("indices"):
            return await self.search(query_embedding, filter=filter, limit=limit)

        async def _do_hybrid_search():
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points/query"

            # Build prefetch queries for both dense and sparse
            prefetch = [
                {
                    "query": query_embedding,
                    "using": "dense",
                    "limit": prefetch_limit,
                },
                {
                    "query": {
                        "indices": query_sparse["indices"],
                        "values": query_sparse["values"],
                    },
                    "using": "bm25",
                    "limit": prefetch_limit,
                },
            ]

            # Main query with RRF fusion
            payload = {
                "prefetch": prefetch,
                "query": {"fusion": "rrf"},  # Reciprocal Rank Fusion
                "limit": limit,
                "with_payload": True,
            }

            # Add filter if provided
            if filter:
                qdrant_filter = self._convert_filter_to_qdrant_format(filter)
                if qdrant_filter:
                    payload["filter"] = qdrant_filter

            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                results = data.get("result", {}).get("points", [])

                # Transform results to standard format
                formatted_results = {
                    "ids": [str(r["id"]) for r in results],
                    "documents": [r["payload"].get("text", "") for r in results],
                    "metadatas": [r["payload"].get("metadata", {}) for r in results],
                    "distances": [1.0 - r.get("score", 0) for r in results],
                    "scores": [r.get("score", 0) for r in results],
                    "total_found": len(results),
                    "search_type": "hybrid_rrf",
                }

                logger.debug(
                    f"Hybrid search: collection={self.collection_name}, "
                    f"found {len(results)} results (RRF fusion)"
                )
                return formatted_results

            except httpx.HTTPStatusError as e:
                error_text = e.response.text if hasattr(e.response, "text") else str(e.response)
                # If hybrid search fails (e.g., collection doesn't have sparse vectors),
                # fall back to dense-only search
                if e.response.status_code == 400 and "sparse" in error_text.lower():
                    logger.warning(
                        f"Hybrid search not available (no sparse vectors), "
                        f"falling back to dense search"
                    )
                    return await self.search(query_embedding, filter=filter, limit=limit)
                logger.error(f"Qdrant hybrid search failed: {e.response.status_code} - {error_text}")
                return {
                    "ids": [],
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                    "scores": [],
                    "total_found": 0,
                    "search_type": "hybrid_rrf",
                    "error": error_text,
                }
            except httpx.RequestError as e:
                logger.error(f"Qdrant hybrid search request error: {e}")
                raise ConnectionError(f"Qdrant connection error: {e}")

        start_time = time.time()
        try:
            result = await _retry_with_backoff(_do_hybrid_search)
            elapsed = time.time() - start_time
            _qdrant_metrics["search_calls"] += 1
            _qdrant_metrics["search_total_time"] += elapsed
            logger.debug(f"Qdrant hybrid search completed in {elapsed * 1000:.2f}ms")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            _qdrant_metrics["errors"] += 1
            logger.error(f"Qdrant hybrid search error after retries: {e}", exc_info=True)
            # Fall back to dense search on error
            return await self.search(query_embedding, filter=filter, limit=limit)

    async def upsert_documents_with_sparse(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        sparse_vectors: list[dict[str, Any]],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
        batch_size: int = 500,
    ) -> dict[str, Any]:
        """
        Insert or update documents with both dense and sparse vectors.

        Args:
            chunks: List of text chunks
            embeddings: List of dense embedding vectors
            sparse_vectors: List of sparse vectors [{"indices": [...], "values": [...]}]
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs
            batch_size: Number of documents per batch

        Returns:
            Dictionary with operation results
        """
        start_time = time.time()
        try:
            client = await self._get_client()
            url = f"/collections/{self.collection_name}/points"

            # Generate IDs if not provided
            if not ids:
                import uuid
                ids = [str(uuid.uuid4()) for _ in range(len(chunks))]

            # Validate input lengths
            if not (len(chunks) == len(embeddings) == len(sparse_vectors) == len(metadatas) == len(ids)):
                raise ValueError(
                    "chunks, embeddings, sparse_vectors, metadatas, and ids must have same length"
                )

            total = len(chunks)
            total_added = 0
            errors = []

            for i in range(0, total, batch_size):
                batch_chunks = chunks[i : i + batch_size]
                batch_embeddings = embeddings[i : i + batch_size]
                batch_sparse = sparse_vectors[i : i + batch_size]
                batch_metadatas = metadatas[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]

                # Build points array with named vectors
                points = []
                for j in range(len(batch_chunks)):
                    point = {
                        "id": batch_ids[j],
                        "vector": {
                            "dense": batch_embeddings[j],
                            "bm25": batch_sparse[j],
                        },
                        "payload": {"text": batch_chunks[j], "metadata": batch_metadatas[j]},
                    }
                    points.append(point)

                payload = {"points": points}
                try:
                    response = await client.put(url, json=payload, params={"wait": "true"})
                    response.raise_for_status()

                    total_added += len(batch_chunks)
                    logger.info(
                        f"Upserted batch {i // batch_size + 1}: {len(batch_chunks)}/{total} documents "
                        f"with sparse vectors to '{self.collection_name}'"
                    )
                except httpx.HTTPStatusError as e:
                    error_msg = f"HTTP {e.response.status_code}"
                    if hasattr(e.response, "text"):
                        error_msg += f": {e.response.text}"
                    errors.append(error_msg)
                    logger.error(f"Qdrant upsert batch failed: {error_msg}")
                except httpx.RequestError as e:
                    error_msg = f"Request error: {e}"
                    errors.append(error_msg)
                    logger.error(f"Qdrant upsert batch request error: {error_msg}")

            if errors:
                return {
                    "success": False,
                    "error": f"Some batches failed: {errors}",
                    "documents_added": total_added,
                    "collection": self.collection_name,
                }

            logger.info(
                f"Successfully upserted {total_added} documents with sparse vectors to '{self.collection_name}'"
            )
            elapsed = time.time() - start_time
            _qdrant_metrics["upsert_calls"] += 1
            _qdrant_metrics["upsert_total_time"] += elapsed
            _qdrant_metrics["upsert_documents_total"] += total_added
            return {
                "success": True,
                "documents_added": total_added,
                "collection": self.collection_name,
                "has_sparse_vectors": True,
            }

        except Exception as e:
            logger.error(f"Error upserting with sparse vectors: {e}", exc_info=True)
            raise
