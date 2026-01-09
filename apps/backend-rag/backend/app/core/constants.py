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


# ============================================================================
# Evidence Score Constants (Agentic RAG)
# ============================================================================


class EvidenceScoreConstants:
    """Constants for evidence score calculation in reasoning.py"""

    # Thresholds
    ABSTAIN_THRESHOLD = 0.3  # Below this score, system abstains from answering
    HIGH_QUALITY_SOURCE_THRESHOLD = 0.3  # Minimum score for a source to be considered high-quality
    MIN_SOURCES_FOR_BONUS = 3  # Minimum number of sources to get bonus score
    KEYWORD_MATCH_THRESHOLD = 0.3  # Minimum keyword match ratio (30%) to add score

    # Score increments
    HIGH_QUALITY_SOURCE_BONUS = 0.5  # Bonus for having at least 1 high-quality source
    MULTIPLE_SOURCES_BONUS = 0.2  # Bonus for having >3 sources
    CONTEXT_KEYWORD_BONUS = 0.3  # Bonus if context contains query keywords
    SUBSTANTIAL_CONTEXT_LENGTH = 500  # Minimum context length (chars) for substantial context bonus

    # Context quality weights
    CONTEXT_QUALITY_KEYWORD_WEIGHT = 0.7  # Weight for keyword matching in context quality
    CONTEXT_QUALITY_COUNT_WEIGHT = 0.3  # Weight for item count in context quality
    PREFERRED_CONTEXT_ITEMS = 5  # Preferred number of context items

    # Maximum score
    MAX_SCORE = 1.0  # Maximum evidence score cap


# ============================================================================
# Intel Service Constants
# ============================================================================


class IntelConstants:
    """Constants for Intel service (intel.py)"""

    # Qdrant collection mappings
    COLLECTIONS = {
        "visa": "visa_oracle",
        "news": "bali_intel_bali_news",
        "immigration": "bali_intel_immigration",
        "bkpm_tax": "bali_intel_bkpm_tax",
        "realestate": "bali_intel_realestate",
        "events": "bali_intel_events",
        "social": "bali_intel_social",
        "competitors": "bali_intel_competitors",
        "bali_news": "bali_intel_bali_news",
        "roundup": "bali_intel_roundup",
    }

    # Visa classification keywords
    VISA_CATEGORIES = {"visa", "immigration", "visa_regulations"}
    VISA_KEYWORDS = [
        "visa",
        "kitas",
        "kitap",
        "voa",
        "immigration",
        "imigrasi",
        "permit",
        "stay permit",
        "residence",
        "b211",
        "e33",
    ]
    MIN_VISA_KEYWORDS = 3  # Minimum visa keyword mentions to classify as visa

    # Default values
    DEFAULT_EXTRACTION_METHOD = "css"
    DEFAULT_TIER = "T2"  # T1, T2, T3


# ============================================================================
# HTTP Client Constants
# ============================================================================


class HttpTimeoutConstants:
    """Constants for HTTP client timeouts across the application"""

    # Standard timeouts (seconds)
    DEFAULT_TIMEOUT = 30.0  # Default timeout for most HTTP requests
    SHORT_TIMEOUT = 10.0  # Short timeout for quick operations
    MEDIUM_TIMEOUT = 60.0  # Medium timeout for longer operations
    LONG_TIMEOUT = 120.0  # Long timeout for very slow operations

    # Service-specific timeouts
    ZOHO_OAUTH_TIMEOUT = 30.0  # Zoho OAuth token exchange
    ZOHO_EMAIL_TIMEOUT = 60.0  # Zoho email API operations
    ZOHO_EMAIL_LONG_TIMEOUT = 120.0  # Zoho email bulk operations
    TELEGRAM_TIMEOUT = 30.0  # Telegram bot API
    AUDIO_TTS_TIMEOUT = 10.0  # Text-to-speech service
    AUDIO_TTS_FALLBACK_TIMEOUT = 5.0  # TTS fallback timeout
    IMAGE_GENERATION_TIMEOUT = 60.0  # Image generation services
    WEB_SEARCH_TIMEOUT = 15.0  # Web search operations
    DEEPSEEK_TIMEOUT = 60.0  # DeepSeek API
    DEEPSEEK_STREAM_TIMEOUT = 120.0  # DeepSeek streaming
    OPENROUTER_TIMEOUT = 10.0  # OpenRouter API
    HEALTH_CHECK_TIMEOUT = 10.0  # Health check endpoints
    HEALTH_CHECK_SHORT_TIMEOUT = 5.0  # Quick health checks
    DIAGNOSTICS_TIMEOUT = 5.0  # Diagnostic tools
    DIAGNOSTICS_SHORT_TIMEOUT = 3.0  # Quick diagnostics
    ANALYTICS_TIMEOUT = 10.0  # Analytics aggregator
    SLACK_WEBHOOK_TIMEOUT = 5.0  # Slack webhook
    DISCORD_WEBHOOK_TIMEOUT = 5.0  # Discord webhook
    INTEL_SCRAPER_TIMEOUT = 30.0  # Intel scraper submissions
    GUARDIAN_AGENT_TIMEOUT = 120.0  # Guardian agent operations

    # Circuit breaker timeout
    CIRCUIT_BREAKER_TIMEOUT = 60.0  # Circuit breaker reset timeout

    # Lock timeout
    MEMORY_LOCK_TIMEOUT = 5.0  # Memory lock acquisition timeout
