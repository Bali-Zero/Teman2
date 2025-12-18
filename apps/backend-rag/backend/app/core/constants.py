"""
NUZANTARA PRIME - Application Constants
Centralized constants to replace magic numbers throughout the codebase
"""

# ============================================================================
# Search Service Constants
# ============================================================================


class SearchConstants:
    """Constants for SearchService"""

    # Score adjustments
    PRICING_SCORE_BOOST = 0.15  # Boost for pricing collection results
    CONFLICT_PENALTY_MULTIPLIER = 0.7  # Penalty for conflicting results
    PRIMARY_COLLECTION_BOOST = 1.1  # Boost for primary collection results
    MAX_SCORE = 1.0  # Maximum score cap


# ============================================================================
# Query Router Constants
# ============================================================================


class RoutingConstants:
    """Constants for QueryRouter"""

    # Confidence thresholds
    CONFIDENCE_THRESHOLD_HIGH = 0.7  # High confidence - use primary only
    CONFIDENCE_THRESHOLD_LOW = 0.3  # Low confidence - try up to 3 fallbacks
    MAX_FALLBACKS = 3  # Maximum number of fallback collections


# ============================================================================
# CRM Service Constants
# ============================================================================


class CRMConstants:
    """Constants for CRM services"""

    # Client confidence thresholds
    CLIENT_CONFIDENCE_THRESHOLD_CREATE = 0.5  # Minimum confidence to create client
    CLIENT_CONFIDENCE_THRESHOLD_UPDATE = 0.6  # Minimum confidence to update client

    # Limits
    SUMMARY_MAX_LENGTH = 500  # Maximum summary length
    PRACTICES_LIMIT = 10  # Maximum practices to retrieve for context


# ============================================================================
# Memory Service Constants
# ============================================================================


class MemoryConstants:
    """Constants for MemoryService"""

    MAX_FACTS = 10  # Maximum profile facts per user
    MAX_SUMMARY_LENGTH = 500  # Maximum conversation summary length


# ============================================================================
# Database Constants
# ============================================================================


class DatabaseConstants:
    """Constants for database operations"""

    # Connection pool settings
    POOL_MIN_SIZE = 2  # Minimum pool size
    POOL_MAX_SIZE = 10  # Maximum pool size
    COMMAND_TIMEOUT = 60  # Command timeout in seconds










