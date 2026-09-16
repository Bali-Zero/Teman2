"""
NUZANTARA PRIME - Application Constants
Centralized constants to replace magic numbers throughout the codebase
"""

from backend.core.collection_registry import resolve_collection_name

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
    HIERARCHICAL_BONUS: float = 0.2
    CONTEXT_KEYWORD_BONUS: float = 0.35  # For keyword matching in context

    # FIXED: ABSTAIN_THRESHOLD raised to 0.15 to properly trigger ABSTAIN for:
    # - Nonsense queries (score ~0.0)
    # - Mismatched results (e.g., KITAS query returning KBLI, score < 0.15)
    # - No relevant context found
    ABSTAIN_THRESHOLD: float = 0.15

    # Confidence level thresholds
    CONFIDENCE_LOW: float = 0.15  # Below this = ABSTAIN
    CONFIDENCE_CAUTIOUS: float = 0.6  # 0.15-0.6 = CAUTIOUS (Tier 1 fallback)
    CONFIDENCE_HIGH: float = 0.6  # Above this = CONFIDENT

    HIGH_QUALITY_SOURCE_THRESHOLD = 0.15  # Minimum source score to be considered "good"
    MIN_SOURCES_FOR_BONUS = 3  # Minimum number of sources to get bonus score
    KEYWORD_MATCH_THRESHOLD = 0.3  # Minimum keyword match ratio (30%) to add score

    # Score increments (legacy - kept for compatibility)
    HIGH_QUALITY_SOURCE_BONUS = 0.5  # Bonus for having at least 1 high-quality source
    MULTIPLE_SOURCES_BONUS = 0.2  # Bonus for having >3 sources
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

    # Qdrant collection mappings — all intel resolves through the canonical registry
    COLLECTIONS = {
        "visa": "visa_oracle",
        "news": resolve_collection_name("balizero_news"),
        "immigration": resolve_collection_name("balizero_news"),
        "bkpm_tax": resolve_collection_name("balizero_news"),
        "realestate": resolve_collection_name("balizero_news"),
        "events": resolve_collection_name("balizero_news"),
        "social": resolve_collection_name("balizero_news"),
        "competitors": resolve_collection_name("balizero_news"),
        "bali_news": resolve_collection_name("balizero_news"),
        "roundup": resolve_collection_name("balizero_news"),
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

    # Scheduling intervals (hours)
    RECENT_TASK_THRESHOLD_HOURS = 24  # Consider task "recent" if run within this time

    # Time ranges (days)
    DUPLICATE_CHECK_DAYS = 7  # Check for duplicates within last N days
    TRENDS_ANALYSIS_DAYS = 30  # Generate trends for last N days

    # Content limits
    MAX_KEY_POINTS = 3  # Maximum key points to extract
    SUMMARY_PREVIEW_LENGTH = 300  # First N characters for summary preview


# ============================================================================
# Tax Consultant Roster (CRM / LKPM)
# ============================================================================


class TaxConsultantConstants:
    """The tax team's @balizero.com addresses.

    Source of truth is `team_members` (Postgres) -- these tuples exist
    because the two DB CHECK constraints that gate `clients.tax_consultant`
    and `lkpm_reports.lkpm_assigned_to` cannot be queried from Python at
    validation time, so the allowed set is mirrored here. The mirror MUST
    agree with migration `319_align_tax_consultant_allowlist_to_team_members.sql`
    (`backend/tests/migrations/test_migration_319_tax_consultant_allowlist_parity.py`
    parses that file's CHECK clauses and asserts equality against
    `CANONICAL` / `LKPM_ASSIGNEES` below -- it does not restate the list by
    hand, so drift between the SQL and this module fails a test instead of
    silently reintroducing a ghost address, which is exactly the defect
    migration 319 cured).

    Two of the addresses this replaces were never real -- a historical
    typo/staff-turnover drift (see migration 319's header for the exact
    spelling) that the old CHECK constraints and four independent Python
    copies of this list (crm_clients.py, lkpm.py, lkpm_deadline_notifier.py,
    and the legacy migration_093 module) all carried, none of them noticing
    the other three had it wrong the same way. This module is the ONE place
    the list lives now; the next staff change is one edit here. (The exact
    ghost strings are deliberately not repeated here --
    `test_tax_consultant_ghost_address_guard.py` sweeps backend/ for them
    and this file is not on its exclusion list.)

    Adding or removing a consultant requires, in the same PR:
      1. this tuple (and LKPM_ASSIGNEES if the person handles LKPM),
      2. a new migration ALTERing both CHECK constraints,
      3. `team_members` itself.
    """

    # The five real tax-team addresses, live in team_members as of 2026-09-15.
    CANONICAL: tuple[str, ...] = (
        "tax@balizero.com",  # Veronika
        "angel.tax@balizero.com",  # Angel
        "kadek.tax@balizero.com",  # Kadek
        "dewaayu.tax@balizero.com",  # Dewa Ayu
        "faysha.tax@balizero.com",  # Faisha -- note the Y
    )

    # LKPM assignment additionally allows Krisna (Executive Consultant, no
    # .tax@ sub-alias -- 110_lkpm_allowlist_krisna.sql).
    LKPM_ASSIGNEES: tuple[str, ...] = (*CANONICAL, "krisna@balizero.com")

    # Veronika is the tax team's point of contact for LKPM deadline
    # escalations (CC'd, not assigned reports herself). An explicit named
    # member, not CANONICAL[0] -- a reorder of the tuple above must not
    # silently change who gets escalation CC.
    MANAGER: str = "tax@balizero.com"

    # The two retired addresses migration 319 moved production rows off of,
    # mapped to their real replacement. The kita frontend dropdown
    # (apps/mouth/src/lib/workspace/roster-directory.ts) still SENDS these
    # as of 2026-09-15 and will until a later mouth PR retires them there
    # too -- `normalize()` below is the write-path cure that keeps those
    # submissions landing on the real address instead of bouncing. This is
    # the ONE place besides the migration itself allowed to hold these
    # literal strings: `test_tax_consultant_ghost_address_guard.py`
    # excludes this file by name for exactly that reason.
    LEGACY_ALIASES: dict[str, str] = {
        "veronika.tax@balizero.com": "tax@balizero.com",
        "faisha.tax@balizero.com": "faysha.tax@balizero.com",
    }

    @classmethod
    def normalize(cls, email: str | None) -> str | None:
        """Resolve a submitted address to its canonical spelling.

        Two rewrites, both of SPELLING and never of identity:
          1. a retired alias -> its real replacement (the kita dropdown still
             sends both retired addresses);
          2. a real address that differs only in case or surrounding
             whitespace -> the canonical form stored in this module.

        Matching is casefolded and whitespace-stripped in both cases. The
        second rule is why the mandate for this change says "no consultant
        excluded from the portal over a legacy SPELLING": before it,
        `" Tax@BaliZero.com "` -- a plausible hand-typed or integration
        submission for a real, active consultant -- was refused with a 422 by
        an allowlist that only ever compared exact bytes.

        Anything that matches neither is returned EXACTLY as received, so the
        allowlist check downstream still judges it on its own terms and the
        error message quotes back what the caller actually sent.
        """
        if email is None:
            return None
        candidate = email.strip().casefold()
        for legacy, real in cls.LEGACY_ALIASES.items():
            if candidate == legacy.casefold():
                return real
        for canonical in cls.LKPM_ASSIGNEES:
            if candidate == canonical.casefold():
                return canonical
        return email


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
    EXTERNAL_API_TIMEOUT = 30.0  # External API calls (WhatsApp, etc.)
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
    JURNAL_TIMEOUT = 30.0  # Jurnal.id API calls

    # Circuit breaker timeout
    CIRCUIT_BREAKER_TIMEOUT = 60.0  # Circuit breaker reset timeout

    # Lock timeout
    MEMORY_LOCK_TIMEOUT = 5.0  # Memory lock acquisition timeout
