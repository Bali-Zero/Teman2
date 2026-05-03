"""
Collection Manager Service
Manages Qdrant collection lifecycle and access

Extracted from SearchService to follow Single Responsibility Principle.
"""

import asyncio
import logging
import time
from typing import Any

from backend.app.core.config import settings
from backend.core.collection_registry import resolve_collection_name
from backend.core.qdrant_db import QdrantClient

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Manages Qdrant collection clients with lazy initialization.

    REFACTORED: Extracted from SearchService to reduce complexity.
    """

    def __init__(self, qdrant_url: str | None = None) -> None:
        """
        Initialize collection manager.

        Args:
            qdrant_url: Optional Qdrant URL (defaults to settings.qdrant_url)
        """
        self.qdrant_url = qdrant_url or settings.qdrant_url
        self._collections_cache: dict[str, QdrantClient] = {}

        # Race condition protection: read-write locks per collection
        # Write locks: exclusive access during ingestion
        # Read semaphores: allow concurrent searches
        self._collection_locks: dict[str, asyncio.Lock] = {}
        self._collection_read_semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock_timeout = 30.0  # seconds (longer for ingestion operations)

        # Freshness tracking: last successful ingest timestamp per collection
        self._collection_last_updated: dict[str, float] = {}

        # Collection definitions (lazy initialization)
        self.collection_definitions = {
            # Memory collections
            "collective_memories": {
                "priority": "high",
                "doc_count": 0,
                "description": "Shared knowledge from users",
            },
            # Core collections
            "bali_zero_pricing_hybrid": {"priority": "high", "doc_count": 29},
            "bali_zero_team": {"priority": "high", "doc_count": 22},
            "visa_oracle": {"priority": "high", "doc_count": 1612},
            "kbli_2025_final": {
                "priority": "high",
                "doc_count": 8886,
                "alias": resolve_collection_name("kbli_2025_final"),
            },
            "tax_genius": {
                "priority": "high",
                "doc_count": 895,
                "alias": resolve_collection_name("tax_genius"),
            },
            "legal_architect": {
                "priority": "high",
                "doc_count": 5041,
                "alias": resolve_collection_name("legal_architect"),
            },
            "legal_unified": {
                "priority": "high",
                "doc_count": 5041,
                "alias": resolve_collection_name("legal_unified"),
            },
            "legal_unified_hybrid": {
                "priority": "high",
                "doc_count": 47959,
                "alias": resolve_collection_name("legal_unified_hybrid"),
            },  # Dec 2025: Hybrid with BM25
            "tax_genius_hybrid": {
                "priority": "high",
                "doc_count": 332,
            },  # Dec 2025: Migrated to hybrid
            "training_conversations_hybrid": {
                "priority": "high",
                "doc_count": 2898,
            },  # Dec 2025: Migrated to hybrid
            "balizero_news": {
                "priority": "high",
                "doc_count": 175,
                "alias": resolve_collection_name("balizero_news"),
                "description": "Intel articles: immigration, tax, bali news, business regulations",
            },
            "zantara_books": {
                "priority": "medium",
                "doc_count": 8923,
                "alias": resolve_collection_name("zantara_books"),
            },
            "cultural_insights": {
                "priority": "low",
                "doc_count": 0,
                "alias": resolve_collection_name("cultural_insights"),
            },
            "tax_updates": {
                "priority": "medium",
                "doc_count": 895,
                "alias": resolve_collection_name("tax_updates"),
            },
            "tax_knowledge": {
                "priority": "medium",
                "doc_count": 895,
                "alias": resolve_collection_name("tax_knowledge"),
            },
            "property_listings": {
                "priority": "medium",
                "doc_count": 29,
                "alias": resolve_collection_name("property_listings"),
            },
            "property_knowledge": {
                "priority": "medium",
                "doc_count": 29,
                "alias": resolve_collection_name("property_knowledge"),
            },
            "legal_updates": {
                "priority": "medium",
                "doc_count": 5041,
                "alias": resolve_collection_name("legal_updates"),
            },
            # Immigration circulars (Surat Edaran Kemnaker/Imigrasi)
            "immigration_circulars": {
                "priority": "high",
                "doc_count": 4,
                "description": "Kemnaker and Imigrasi circular letters on TKA procedures",
            },
        }

        logger.info("✅ CollectionManager initialized (lazy loading enabled)")

    def get_collection(self, name: str) -> QdrantClient | None:
        """
        Get collection client (lazy initialization).

        Args:
            name: Collection name

        Returns:
            QdrantClient instance or None if collection not found
        """
        # Check cache first
        if name in self._collections_cache:
            return self._collections_cache[name]

        # Check if collection is defined
        if name not in self.collection_definitions:
            logger.warning(f"⚠️ Unknown collection: {name}")
            return None

        # Get actual collection name (handle aliases)
        definition = self.collection_definitions[name]
        actual_name = definition.get("alias") or name

        # Create client (lazy initialization)
        try:
            client = QdrantClient(qdrant_url=self.qdrant_url, collection_name=actual_name)
            self._collections_cache[name] = client
            logger.debug(f"✅ Lazy-loaded collection: {name} -> {actual_name}")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to create collection client for {name}: {e}")
            return None

    def get_all_collections(self) -> dict[str, QdrantClient]:
        """
        Get all collection clients (pre-initializes all collections).

        Use sparingly - prefer get_collection() for lazy loading.

        Returns:
            Dictionary mapping collection names to clients
        """
        collections = {}
        for name in self.collection_definitions:
            client = self.get_collection(name)
            if client:
                collections[name] = client
        return collections

    def list_collections(self) -> list[str]:
        """
        List all available collection names.

        Returns:
            List of collection names
        """
        return list(self.collection_definitions.keys())

    def get_collection_info(self, name: str) -> dict[str, Any] | None:
        """
        Get collection metadata.

        Args:
            name: Collection name

        Returns:
            Collection info dict or None if not found
        """
        if name not in self.collection_definitions:
            return None

        definition = self.collection_definitions[name].copy()
        definition["actual_name"] = definition.get("alias") or name
        definition["last_updated"] = self._collection_last_updated.get(name)
        return definition

    def get_collection_freshness(self) -> dict[str, dict[str, Any]]:
        """
        Get freshness information for all collections.

        Returns a dict keyed by collection name with last_updated timestamp
        and age_seconds (time since last ingest).

        Returns:
            Dict mapping collection names to freshness info
        """
        now = time.time()
        result: dict[str, dict[str, Any]] = {}
        for name in self.collection_definitions:
            last_updated = self._collection_last_updated.get(name)
            result[name] = {
                "last_updated": last_updated,
                "age_seconds": round(now - last_updated, 1) if last_updated else None,
                "priority": self.collection_definitions[name].get("priority", "unknown"),
            }
        return result

    async def search_with_lock(
        self,
        collection_name: str,
        query_embedding: list[float],
        limit: int = 5,
        filter: dict | None = None,
    ) -> dict[str, Any]:
        """
        Search collection with read lock protection.

        RACE CONDITION PROTECTION: Uses read semaphore to allow concurrent
        searches while blocking during ingestion.

        Args:
            collection_name: Collection to search
            query_embedding: Query embedding vector
            limit: Max results
            filter: Optional Qdrant filter

        Returns:
            Search results dict
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return {"documents": [], "ids": [], "metadatas": [], "distances": []}

        semaphore = self._collection_read_semaphores[collection_name]

        async with semaphore:
            # Multiple searches can proceed concurrently
            return await collection.search(
                query_embedding=query_embedding, filter=filter, limit=limit,
            )

    async def ingest_with_lock(
        self,
        collection_name: str,
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Ingest documents with write lock protection.

        RACE CONDITION PROTECTION: Uses write lock to ensure exclusive access
        during ingestion, preventing corruption during concurrent searches.

        Args:
            collection_name: Collection to ingest into
            documents: List of document texts
            embeddings: List of embedding vectors
            metadatas: Optional metadata list
            ids: Optional ID list

        Returns:
            Ingestion result dict

        Raises:
            RuntimeError: If lock acquisition times out
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection {collection_name} not found")

        lock = self._collection_locks[collection_name]

        try:
            # Acquire write lock with timeout
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
            try:
                # Exclusive write access
                result = await collection.upsert_documents(
                    chunks=documents,
                    embeddings=embeddings,
                    metadatas=metadatas or [],
                    ids=ids or [],
                )
                # Record freshness timestamp on successful ingest
                now = time.time()
                self._collection_last_updated[collection_name] = now
                try:
                    from backend.app.metrics import metrics_collector
                    metrics_collector.set_collection_last_updated(collection_name, now)
                except Exception:
                    pass
                return result
            finally:
                lock.release()
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Ingestion lock timeout for {collection_name} (timeout: {self._lock_timeout}s)",
            )
