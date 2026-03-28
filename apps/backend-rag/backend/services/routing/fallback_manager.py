"""
Fallback Manager Service
Responsibility: Manage fallback chains and collection selection
"""

import logging
from typing import Literal

from backend.app.core.constants import RoutingConstants

logger = logging.getLogger(__name__)

CollectionName = Literal[
    "visa_oracle",
    "immigration_circulars",  # Kemnaker/Imigrasi circulars (SE, policy updates)
    "kbli_2025_final",
    "tax_genius",
    "legal_architect",
    "legal_unified",
    "tax_updates",
    "tax_knowledge",
    "legal_updates",
    "bali_zero_pricing_hybrid",
    "training_conversations_hybrid",
    "balizero_news",
]


class FallbackManagerService:
    """
    Service for managing fallback chains.

    Responsibility: Determine which collections to query based on confidence and fallback chains.
    """

    # Phase 3: Smart Fallback Chains
    # Define fallback priority for each primary collection
    FALLBACK_CHAINS = {
        "visa_oracle": [
            "immigration_circulars",
            "legal_architect",
            "tax_genius",
        ],  # Circulars first for TKA/policy
        "immigration_circulars": [
            "visa_oracle",
            "legal_architect",
        ],  # Circulars fallback to main visa
        "kbli_2025_final": ["legal_architect", "tax_genius", "visa_oracle"],
        "tax_genius": [
            "tax_knowledge",
            "tax_updates",
            "legal_architect",
        ],
        "tax_knowledge": ["tax_genius", "tax_updates", "legal_architect"],
        "tax_updates": ["tax_genius", "tax_knowledge", "legal_updates"],
        "legal_architect": ["legal_updates", "kbli_2025_final", "tax_genius"],
        "legal_updates": ["legal_architect", "tax_updates", "visa_oracle"],
        "training_conversations_hybrid": [
            "legal_architect",
            "tax_genius",
            "kbli_2025_final",
        ],  # Business setup fallback to legal/tax/kbli
        "legal_unified": [
            "legal_architect",
            "kbli_2025_final",
            "tax_genius",
            "visa_oracle",
        ],  # Default legal corpus fallback to specialized oracles
        "bali_zero_pricing_hybrid": [
            "legal_unified",
            "tax_genius",
            "visa_oracle",
        ],
        "balizero_news": [
            "legal_unified",
            "visa_oracle",
            "kbli_2025_final",
        ],
    }

    CONFIDENCE_THRESHOLD_HIGH = RoutingConstants.CONFIDENCE_THRESHOLD_HIGH
    CONFIDENCE_THRESHOLD_LOW = RoutingConstants.CONFIDENCE_THRESHOLD_LOW

    def get_fallback_collections(
        self, primary_collection: CollectionName, confidence: float, max_fallbacks: int = 3,
    ) -> list[CollectionName]:
        """
        Get list of collections to try based on confidence.

        Strategy:
        - High confidence (>0.7): Primary only
        - Medium confidence (0.3-0.7): Primary + 1 fallback
        - Low confidence (<0.3): Primary + up to 3 fallbacks

        Args:
            primary_collection: Initially routed collection
            confidence: Confidence score (0.0 - 1.0)
            max_fallbacks: Maximum fallbacks to return

        Returns:
            List of collections to query in order (primary first)
        """
        collections = [primary_collection]

        # Determine number of fallbacks based on confidence
        if confidence >= self.CONFIDENCE_THRESHOLD_HIGH:
            # High confidence - primary only
            num_fallbacks = 0
        elif confidence >= self.CONFIDENCE_THRESHOLD_LOW:
            # Medium confidence - try 1 fallback
            num_fallbacks = 1
        else:
            # Low confidence - try up to 3 fallbacks
            num_fallbacks = min(max_fallbacks, 3)

        # Add fallbacks from chain
        if num_fallbacks > 0 and primary_collection in self.FALLBACK_CHAINS:
            fallback_chain = self.FALLBACK_CHAINS[primary_collection]
            collections.extend(fallback_chain[:num_fallbacks])

        return collections

    def get_fallback_chain(self, primary_collection: CollectionName) -> list[CollectionName]:
        """
        Get full fallback chain for a collection.

        Args:
            primary_collection: Primary collection name

        Returns:
            List of collections in fallback order
        """
        if primary_collection not in self.FALLBACK_CHAINS:
            return [primary_collection]

        return [primary_collection] + self.FALLBACK_CHAINS[primary_collection]
