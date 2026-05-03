"""
Hierarchical retrieval for Indonesian politics KB.

Parent-child chunking: parent = full record text, child = claim-level sentences.
Query matches on children, retrieves parents for context.
"""

from backend.kb.politics.hierarchical.chunker import HierarchicalChunker
from backend.kb.politics.hierarchical.extractor import ClaimExtractor
from backend.kb.politics.hierarchical.retriever import HierarchicalRetriever

__all__ = ["HierarchicalChunker", "ClaimExtractor", "HierarchicalRetriever"]
