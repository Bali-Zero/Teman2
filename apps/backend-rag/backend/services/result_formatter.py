"""
Result formatting utilities for vector database search results.

Extracted from SearchService to improve modularity and testability.
"""

from typing import Any


def format_search_results(
    raw_results: dict[str, Any],
    collection_name: str,
    primary_collection: str | None = None,
) -> list[dict[str, Any]]:
    """Format raw vector database results with score boosting and metadata enrichment.

    Transforms raw Qdrant/ChromaDB results into standardized format with:
    - Normalized scores: Distance converted to similarity (0-1 range)
    - Collection-specific boosts: Pricing/primary collection prioritization
    - Metadata enrichment: Source tracking, priority flags
    - Citation tracking: Collection origin for multi-collection searches

    Score Calculation:
    1. Base score: 1 / (1 + distance) - converts cosine distance to similarity
    2. Primary boost: +20% for results from primary collection
    3. Pricing boost: +15% for bali_zero_pricing collection
    4. Team boost: +15% for bali_zero_team collection
    5. Capping: Max score = 0.99 to preserve ranking stability

    Args:
        raw_results: Raw DB results with keys:
            - documents (list[str]): Document texts
            - distances (list[float]): Cosine distances
            - metadatas (list[dict]): Document metadata
            - ids (list[str]): Document IDs
        collection_name: Source collection name for this batch
        primary_collection: If set, boost results from this collection

    Returns:
        List of formatted result dicts:
            - id (str): Document ID
            - text (str): Document content
            - metadata (dict): Enriched metadata with source tracking
            - score (float): Normalized similarity score (0-1)

    Note:
        - Empty results: Returns [] if no documents in raw_results
        - Score precision: Rounded to 4 decimal places for consistency
        - Metadata preservation: Original metadata retained, new fields added
        - Multi-collection: Adds source_collection and is_primary flags

    Example:
        >>> raw = {
        ...     "ids": ["doc1"],
        ...     "documents": ["KITAS E33G info..."],
        ...     "distances": [0.3],
        ...     "metadatas": [{"type": "visa"}]
        ... }
        >>> results = format_search_results(
        ...     raw, "bali_zero_pricing", primary_collection="visa_oracle"
        ... )
        >>> print(results[0]["score"])  # 0.9185 (base + pricing boost)
    """
    from app.core.constants import SearchConstants

    formatted_results = []

    for i in range(len(raw_results.get("documents", []))):
        distance = (
            raw_results["distances"][i] if i < len(raw_results.get("distances", [])) else 1.0
        )
        # Validate distance to avoid division by zero
        # Cosine distance should always be >= 0, but validate for safety
        if distance < 0:
            distance = 0.0  # Clamp negative distances to 0
        if distance == -1.0:
            # Avoid division by zero (shouldn't happen with cosine distance, but be safe)
            distance = 1.0

        score = 1 / (1 + distance)

        # Apply collection-specific boosts
        if primary_collection and collection_name == primary_collection:
            score = min(
                SearchConstants.MAX_SCORE, score * SearchConstants.PRIMARY_COLLECTION_BOOST
            )

        if collection_name == "bali_zero_pricing":
            score = min(SearchConstants.MAX_SCORE, score + SearchConstants.PRICING_SCORE_BOOST)

        if collection_name == "bali_zero_team":
            score = min(SearchConstants.MAX_SCORE, score + SearchConstants.PRICING_SCORE_BOOST)

        # Get metadata (create copy to avoid mutating shared references)
        metadata = (
            dict(raw_results["metadatas"][i]) if i < len(raw_results.get("metadatas", [])) else {}
        )

        # Add collection tracking metadata if multi-collection search
        if primary_collection:
            metadata["source_collection"] = collection_name
            metadata["is_primary"] = collection_name == primary_collection

        # Add pricing priority flag
        if collection_name == "bali_zero_pricing":
            metadata["pricing_priority"] = "high"

        # Get document content
        doc_content = (
            raw_results["documents"][i] if i < len(raw_results.get("documents", [])) else ""
        )

        formatted_results.append(
            {
                "id": raw_results["ids"][i] if i < len(raw_results.get("ids", [])) else None,
                "text": doc_content,
                "metadata": metadata,
                "score": round(score, 4),
            }
        )

    return formatted_results

