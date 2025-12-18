"""
Collection Manager Service
Manages Qdrant collection lifecycle and access

Extracted from SearchService to follow Single Responsibility Principle.
"""

import logging
from typing import Any

from core.qdrant_db import QdrantClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Manages Qdrant collection clients with lazy initialization.

    REFACTORED: Extracted from SearchService to reduce complexity.
    """

    def __init__(self, qdrant_url: str | None = None):
        """
        Initialize collection manager.

        Args:
            qdrant_url: Optional Qdrant URL (defaults to settings.qdrant_url)
        """
        self.qdrant_url = qdrant_url or settings.qdrant_url
        self._collections_cache: dict[str, QdrantClient] = {}

        # Collection definitions (lazy initialization)
        self.collection_definitions = {
            # Memory collections
            "collective_memories": {
                "priority": "high",
                "doc_count": 0,
                "description": "Shared knowledge from users",
            },
            # Core collections
            "bali_zero_pricing": {"priority": "high", "doc_count": 29},
            "bali_zero_team": {"priority": "high", "doc_count": 22},
            "visa_oracle": {"priority": "high", "doc_count": 1612},
            "kbli_eye": {"priority": "high", "doc_count": 8886, "alias": "kbli_unified"},
            "tax_genius": {"priority": "high", "doc_count": 895},
            "legal_architect": {"priority": "high", "doc_count": 5041, "alias": "legal_unified"},
            "legal_unified": {"priority": "high", "doc_count": 5041},
            "kb_indonesian": {"priority": "medium", "doc_count": 0, "alias": "knowledge_base"},
            "kbli_comprehensive": {
                "priority": "medium",
                "doc_count": 8886,
                "alias": "kbli_unified",
            },
            "kbli_unified": {"priority": "high", "doc_count": 8886},
            "zantara_books": {"priority": "medium", "doc_count": 8923, "alias": "knowledge_base"},
            "cultural_insights": {"priority": "low", "doc_count": 0, "alias": "knowledge_base"},
            "tax_updates": {"priority": "medium", "doc_count": 895, "alias": "tax_genius"},
            "tax_knowledge": {"priority": "medium", "doc_count": 895, "alias": "tax_genius"},
            "property_listings": {
                "priority": "medium",
                "doc_count": 29,
                "alias": "property_unified",
            },
            "property_knowledge": {
                "priority": "medium",
                "doc_count": 29,
                "alias": "property_unified",
            },
            "legal_updates": {"priority": "medium", "doc_count": 5041, "alias": "legal_unified"},
            "legal_intelligence": {
                "priority": "medium",
                "doc_count": 5041,
                "alias": "legal_unified",
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
        for name in self.collection_definitions.keys():
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
        return definition










