"""Canonical logical-to-physical Qdrant collection registry."""

from __future__ import annotations

from typing import Final

CANONICAL_LOGICAL_COLLECTIONS: Final[tuple[str, ...]] = (
    "bali_zero_pricing_hybrid",
    "visa_oracle",
    "kbli_2025_final",
    "tax_genius",
    "legal_unified",
    "training_conversations_hybrid",
    "immigration_circulars",
    "balizero_news",
)

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
    "balizero_news": "balizero_news",
    "tax_updates": "tax_genius_hybrid",
    "tax_knowledge": "tax_genius_hybrid",
    "legal_updates": "legal_unified_hybrid_hybrid",
    "legal_intelligence": "legal_unified_hybrid_hybrid",
}

CANONICAL_COLLECTION_ALIASES: Final[dict[str, str]] = {
    "bali_zero_pricing_hybrid": "bali_zero_pricing_hybrid",
    "visa_oracle": "visa_oracle",
    "kbli_2025_final": "kbli_2025_final",
    "kbli_2025_final_hybrid": "kbli_2025_final",
    "tax_genius": "tax_genius",
    "tax_genius_hybrid": "tax_genius",
    "tax_updates": "tax_genius",
    "tax_knowledge": "tax_genius",
    "legal_architect": "legal_unified",
    "legal_unified": "legal_unified",
    "legal_unified_hybrid": "legal_unified",
    "legal_unified_hybrid_hybrid": "legal_unified",
    "legal_updates": "legal_unified",
    "legal_intelligence": "legal_unified",
    "training_conversations_hybrid": "training_conversations_hybrid",
    "immigration_circulars": "immigration_circulars",
    "balizero_news": "balizero_news",
    "intel_authoritative_sources": "balizero_news",
}


def resolve_collection_name(collection_name: str) -> str:
    """Resolve a logical collection name to the live physical Qdrant collection."""
    return LOGICAL_TO_PHYSICAL_COLLECTIONS.get(collection_name, collection_name)


def is_known_collection(collection_name: str) -> bool:
    """Return True when the collection name is defined in the logical registry."""
    return collection_name in LOGICAL_TO_PHYSICAL_COLLECTIONS


def get_canonical_collection_names() -> tuple[str, ...]:
    """Return the canonical logical collection names exposed across the platform."""
    return CANONICAL_LOGICAL_COLLECTIONS


def canonicalize_collection_name(collection_name: str) -> str:
    """Normalize aliases and physical names back to the canonical logical name."""
    return CANONICAL_COLLECTION_ALIASES.get(collection_name, collection_name)
