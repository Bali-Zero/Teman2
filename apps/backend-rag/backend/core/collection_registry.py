"""Canonical logical-to-physical Qdrant collection registry."""

from __future__ import annotations

from typing import Final

SKILLS_MIRROR_COLLECTION: Final[str] = "bali_zero_skills_hybrid"

CANONICAL_LOGICAL_COLLECTIONS: Final[tuple[str, ...]] = (
    "bali_zero_pricing_hybrid",
    "visa_oracle",
    "kbli_2025_final",
    "tax_genius",
    "legal_unified",
    "training_conversations_hybrid",
    "immigration_circulars",
    "balizero_news",
    # R5 AIL #1 (2026-05-17): Mata-Garuda skills/reflections/insights mirrored
    # to Qdrant Cloud (613 docs). Replaces local-only bali_zero_skills_local.
    SKILLS_MIRROR_COLLECTION,
    # Sprint 2 Shadow Graphing (2026-04-25): NLM-extracted claims projected
    # offline into Qdrant for sub-second runtime retrieval. Schema is
    # NLMShadowChunk (NOT HierarchicalChunk) — kept fully separate so
    # legal_unified / visa_oracle / etc. payloads stay rigid.
    "nlm_shadow_hybrid",
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
    # R5 AIL #1: skills on Qdrant Cloud
    SKILLS_MIRROR_COLLECTION: SKILLS_MIRROR_COLLECTION,
    # Sprint 2 Shadow Graphing
    "nlm_shadow_hybrid": "nlm_shadow_hybrid",
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
    "nlm_shadow_hybrid": "nlm_shadow_hybrid",
    # R5 AIL #1
    SKILLS_MIRROR_COLLECTION: SKILLS_MIRROR_COLLECTION,
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
