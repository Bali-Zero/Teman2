"""
RAG (Retrieval-Augmented Generation) services.

Contains agent-based RAG, hybrid retrieval, knowledge graph integration,
and vision RAG capabilities.
"""

from backend.services.rag.hybrid_search import (
    HybridSearchService,
    get_hybrid_search_service,
)

__all__ = [
    "HybridSearchService",
    "get_hybrid_search_service",
]
