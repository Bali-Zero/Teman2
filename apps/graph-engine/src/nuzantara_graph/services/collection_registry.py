"""Canonical logical-to-physical Qdrant collection registry for graph-engine."""

from __future__ import annotations

from typing import Final

DEFAULT_COLLECTION: Final[str] = "legal_unified"

LOGICAL_TO_PHYSICAL_COLLECTIONS: Final[dict[str, str]] = {
    "bali_zero_pricing_hybrid": "bali_zero_pricing_hybrid",
    "visa_oracle": "visa_oracle",
    "kbli_2025_final": "kbli_2025_final_hybrid",
    "tax_genius": "tax_genius_hybrid",
    "tax_genius_hybrid": "tax_genius_hybrid",
    "legal_architect": "legal_unified_hybrid_hybrid",
    "legal_unified": "legal_unified_hybrid_hybrid",
    "legal_unified_hybrid": "legal_unified_hybrid_hybrid",
    "training_conversations_hybrid": "training_conversations_hybrid",
    "immigration_circulars": "immigration_circulars",
    "balizero_news": "intel_authoritative_sources",
    "tax_updates": "tax_genius_hybrid",
    "tax_knowledge": "tax_genius_hybrid",
    "legal_updates": "legal_unified_hybrid_hybrid",
    "legal_intelligence": "legal_unified_hybrid_hybrid",
    "v6_cache_vectors": "v6_cache_vectors",
}


def resolve_collection_name(collection_name: str) -> str:
    """Resolve a logical collection name to the live physical Qdrant collection."""
    return LOGICAL_TO_PHYSICAL_COLLECTIONS.get(collection_name, collection_name)
