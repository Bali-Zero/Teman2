"""
Cultural Insights Service
Manages cultural insights storage and retrieval from Qdrant

Extracted from SearchService to follow Single Responsibility Principle.
"""

import hashlib
import logging
from typing import Any

from core.embeddings import EmbeddingsGenerator

# from services.collection_manager import CollectionManager

logger = logging.getLogger(__name__)


class CulturalInsightsService:
    """
    Manages cultural insights storage and retrieval.

    REFACTORED: Extracted from SearchService to reduce complexity.

    Responsibilities:
    - Add cultural insights to Qdrant
    - Query cultural insights by semantic search
    - Format cultural insights for prompt injection

    Does NOT handle:
    - General document search (use SearchService)
    - Collection management (use CollectionManager)
    """

    def __init__(
        self,
        collection_manager: Any,
        embedder: EmbeddingsGenerator,
    ):
        """
        Initialize cultural insights service.

        Args:
            collection_manager: CollectionManager instance for accessing collections
            embedder: EmbeddingsGenerator for creating embeddings
        """
        self.collection_manager = collection_manager
        self.embedder = embedder
        self.collection_name = "cultural_insights"

        logger.info("✅ CulturalInsightsService initialized")

    async def add_insight(self, text: str, metadata: dict[str, Any]) -> bool:
        """
        Add cultural insight to Qdrant.

        Called by CulturalKnowledgeGenerator to store generated insights.

        Args:
            text: Cultural insight content
            metadata: Metadata dict with topic, language, when_to_use, tone, etc.

        Returns:
            bool: Success status
        """
        try:
            # Generate unique ID from content hash
            content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            doc_id = f"cultural_{metadata.get('topic', 'unknown')}_{content_hash[:8]}"

            # Generate embedding
            embedding = self.embedder.generate_query_embedding(text)

            # Get cultural insights collection
            cultural_db = self.collection_manager.get_collection(self.collection_name)
            if not cultural_db:
                logger.error(
                    f"❌ Cultural insights collection '{self.collection_name}' not available"
                )
                return False

            # Convert list fields to strings for Qdrant compatibility
            chroma_metadata = {**metadata}
            if "when_to_use" in chroma_metadata and isinstance(
                chroma_metadata["when_to_use"], list
            ):
                chroma_metadata["when_to_use"] = ", ".join(chroma_metadata["when_to_use"])

            # Upsert (async)
            await cultural_db.upsert_documents(
                chunks=[text], embeddings=[embedding], metadatas=[chroma_metadata], ids=[doc_id]
            )

            logger.info(f"✅ Added cultural insight: {metadata.get('topic', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add cultural insight: {e}", exc_info=True)
            return False

    async def query_insights(
        self, query: str, when_to_use: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        """
        Query cultural insights from Qdrant using semantic search.

        Args:
            query: Search query (user message)
            when_to_use: Optional filter by usage context (e.g., "first_contact", "greeting")
            limit: Max results

        Returns:
            List of cultural insight dicts with content and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.generate_query_embedding(query)

            # NOTE: Qdrant filtering is limited - we rely on semantic search instead
            # The when_to_use metadata is stored as comma-separated string, but Qdrant
            # doesn't support substring matching. Semantic search will naturally rank
            # relevant cultural insights higher based on the query content.
            chroma_filter = None

            # Search cultural_insights collection
            cultural_db = self.collection_manager.get_collection(self.collection_name)
            if not cultural_db:
                logger.warning(
                    f"⚠️ Cultural insights collection '{self.collection_name}' not available"
                )
                return []

            raw_results = await cultural_db.search(
                query_embedding=query_embedding, filter=chroma_filter, limit=limit
            )

            # Format results
            formatted_results = []
            for i in range(len(raw_results.get("documents", []))):
                distance = (
                    raw_results["distances"][i]
                    if i < len(raw_results.get("distances", []))
                    else 1.0
                )
                score = 1 / (1 + distance)

                formatted_results.append(
                    {
                        "content": (
                            raw_results["documents"][i]
                            if i < len(raw_results.get("documents", []))
                            else ""
                        ),
                        "metadata": (
                            raw_results["metadatas"][i]
                            if i < len(raw_results.get("metadatas", []))
                            else {}
                        ),
                        "score": round(score, 4),
                    }
                )

            logger.info(f"🌴 Retrieved {len(formatted_results)} cultural insights for query")
            return formatted_results

        except Exception as e:
            logger.error(f"❌ Cultural insights query failed: {e}", exc_info=True)
            return []

    async def get_topics_coverage(self) -> dict[str, int]:
        """
        Get coverage statistics for cultural topics.

        Returns:
            Dict mapping topic -> count of insights
        """
        try:
            # This would require scanning all documents in the collection
            # For now, return empty dict (can be implemented later if needed)
            logger.warning("⚠️ get_topics_coverage() not yet implemented")
            return {}
        except Exception as e:
            logger.error(f"❌ Failed to get cultural topics coverage: {e}")
            return {}










