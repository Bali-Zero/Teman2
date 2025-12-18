"""
ZANTARA RAG - Query Router
Intelligent routing between multiple Qdrant collections based on query content

Phase 3 Enhancement: Smart Fallback Chain Agent
- Confidence scoring for routing decisions
- Automatic fallback to secondary collections when confidence is low
- Configurable fallback chains per domain
- Detailed logging and metrics

REFACTORED: Uses sub-services following Single Responsibility Principle
- KeywordMatcherService: Keyword matching
- ConfidenceCalculatorService: Confidence calculation
- FallbackManagerService: Fallback chain management
- PriorityOverrideService: Priority override detection
- RoutingStatsService: Statistics tracking
"""

import logging
from typing import Any, Literal

from app.core.constants import RoutingConstants
from services.routing import (
    ConfidenceCalculatorService,
    FallbackManagerService,
    KeywordMatcherService,
    PriorityOverrideService,
    RoutingStatsService,
)

logger = logging.getLogger(__name__)

# Phase 2/3: Extended collection support (5 → 15 collections with Oracle + expanded KBLI/Legal/Tax + Team)
CollectionName = Literal[
    "visa_oracle",
    "kbli_eye",
    "kbli_comprehensive",
    "tax_genius",
    "legal_architect",
    "zantara_books",
    "tax_updates",
    "tax_knowledge",
    "property_listings",
    "property_knowledge",
    "legal_updates",
    "bali_zero_pricing",
    "kb_indonesian",
    "cultural_insights",
    "bali_zero_team",
]


class QueryRouter:
    """
    3-Layer Routing System:
    1. Keyword matching (fast, <1ms) - handles 99% of queries
    2. Semantic analysis (future) - handles ambiguous queries
    3. LLM fallback (future) - handles edge cases

    Current implementation: Layer 1 (keyword-based routing)
    """

    # Domain-specific keywords for multi-collection routing
    # Generic patterns only - no specific codes (B211, C1, E23, etc. are in database)
    VISA_KEYWORDS = [
        "visa",
        "immigration",
        "imigrasi",
        "passport",
        "paspor",
        "sponsor",
        "stay permit",
        "tourist visa",
        "social visa",
        "work permit",
        "visit visa",
        "long stay",
        "permit",
        "residence",
        "immigration office",
        "dirjen imigrasi",
    ]

    KBLI_KEYWORDS = [
        "kbli",
        "business classification",
        "klasifikasi baku",
        "oss",
        "nib",
        "risk-based",
        "berbasis risiko",
        "business license",
        "izin usaha",
        "standard industrial",
        "kode usaha",
        "sektor usaha",
        "business sector",
        "foreign ownership",
        "kepemilikan asing",
        "negative list",
        "dnpi",
        "business activity",
        "kegiatan usaha",
        "kode klasifikasi",
    ]

    TAX_KEYWORDS = [
        "tax",
        "pajak",
        "tax reporting",
        "withholding tax",
        "vat",
        "income tax",
        "corporate tax",
        "fiscal",
        "tax compliance",
        "tax calculation",
        "tax registration",
        "tax filing",
        "tax office",
        "direktorat jenderal pajak",
    ]

    # Tax Genius specific keywords (for procedural/calculation queries)
    TAX_GENIUS_KEYWORDS = [
        "tax calculation",
        "calculate tax",
        "tax rate",
        "how to calculate",
        "tax example",
        "example",
        "tax procedure",
        "step by step",
        "menghitung pajak",
        "perhitungan pajak",
        "cara menghitung",
        "tax service",
        "bali zero service",
        "pricelist",
        "tarif pajak",
    ]

    LEGAL_KEYWORDS = [
        "company",
        "foreign investment",
        "limited liability",
        "company formation",
        "incorporation",
        "deed",
        "notary",
        "notaris",
        "shareholder",
        "business entity",
        "legal entity",
        "law",
        "hukum",
        "regulation",
        "peraturan",
        "legal compliance",
        "contract",
        "perjanjian",
        # Italian keywords
        "legge",
        "normativa",
        "norma",
        "regolamento",
        "contratto",
        "atto",
        "notaio",
        # Code patterns (UU-, PP-, etc.)
        "uu-",
        "undang-undang",
        "pp-",
        "peraturan pemerintah",
        "keputusan menteri",
        "keppres",
        "perpres",
        "permen",
        "pasal",
        "ayat",
    ]

    # Property-related keywords (generic patterns only - no specific locations)
    PROPERTY_KEYWORDS = [
        "property",
        "properti",
        "villa",
        "land",
        "tanah",
        "house",
        "rumah",
        "apartment",
        "apartemen",
        "real estate",
        "listing",
        "for sale",
        "dijual",
        "lease",
        "sewa",
        "rent",
        "rental",
        "leasehold",
        "freehold",
        "investment property",
        "development",
        "land bank",
        "zoning",
        "setback",
        "due diligence",
        "title deed",
        "sertipikat",
        "ownership structure",
    ]

    # Team-specific keywords (generic patterns only - no specific names)
    TEAM_KEYWORDS = [
        "team",
        "tim",
        "staff",
        "employee",
        "karyawan",
        "personil",
        "team member",
        "colleague",
        "consultant",
        "specialist",
        "setup specialist",
        "tax specialist",
        "consulting",
        "accounting",
        "founder",
        "fondatore",
        "ceo",
        "director",
        "manager",
        "lead",
        "contact",
        "contattare",
        "contatta",
        "whatsapp",
        "email",
        "dipartimento",
        "division",
        "department",
        "professionista",
        "expert",
        "consulente",
    ]

    # Backend Services keywords (for technical/API queries)
    BACKEND_SERVICES_KEYWORDS = [
        "backend",
        "api endpoint",
        "endpoint",
        "servizio backend",
        "backend service",
        "python tool",
        "tool python",
        "zantara tool",
        "get_pricing",
        "search_team_member",
        "tool executor",
        "handler",
        "typescript handler",
        "crm service",
        "conversation service",
        "memory service",
        "agentic function",
        "api documentation",
        "come posso chiamare",
        "how to call",
        "come accedere",
        "how to access",
        "quale endpoint",
        "which endpoint",
        "api disponibili",
        "available api",
        "servizi disponibili",
        "available services",
        "postgresql",
        "qdrant",
        "vector database",
        "database vettoriale",
        "auto-crm",
        "client journey",
        "compliance monitoring",
        "dynamic pricing",
        "cross-oracle synthesis",
        "crm",
        "conversazione",
        "conversation",
        "memoria",
        "memory",
        "semantic",
        "semantica",
        "salvare",
        "save",
        "caricare",
        "load",
        "database",
        "client information",
        "informazioni cliente",
        "pratica",
        "practice",
        "interazione",
        "interaction",
        "log interaction",
        "loggare",
    ]

    # NEW: Enumeration keywords that trigger team data retrieval
    TEAM_ENUMERATION_KEYWORDS = [
        "lista",
        "elenco",
        "tutti",
        "complete",
        "completa",
        "intero",
        "mostrami",
        "mostra",
        "mostrare",
        "elenca",
        "elenchiamo",
        "elenca",
        "chi sono",
        "chi lavora",
        "quante persone",
        "quanti membri",
        "chi fa parte",
        "chi c'è",
        "in totale",
        "insieme",
        "tutti i membri",
        "l'intero team",
        "il team completo",
    ]

    # Phase 2: Update/news keywords (for tax_updates & legal_updates)
    UPDATE_KEYWORDS = [
        "update",
        "updates",
        "pembaruan",
        "recent",
        "terbaru",
        "latest",
        "new",
        "news",
        "berita",
        "announcement",
        "pengumuman",
        "change",
        "perubahan",
        "amendment",
        "revisi",
        "revision",
        "effective date",
        "berlaku",
        "regulation update",
        "policy change",
        "what's new",
        "latest news",
    ]

    # Consolidated high-signal keywords frequently used by Bali Zero users
    # Used for lightweight diagnostics in get_routing_stats()
    BALI_ZERO_KEYWORDS = [
        # Core brands/terms
        "bali",
        "zero",
        "bali zero",
        "zantara",
        # Immigration
        "visa",
        "kitas",
        "kitap",
        "imigrasi",
        "immigration",
        # Business/KBLI
        "kbli",
        "oss",
        "nib",
        "pt pma",
        "bkpm",
        # Tax
        "tax",
        "pajak",
        "npwp",
        "pph",
        "ppn",
        # Legal
        "legal",
        "notary",
        "notaris",
        "akta",
    ]

    # Keywords that indicate philosophical/technical knowledge
    BOOKS_KEYWORDS = [
        # Philosophy
        "plato",
        "aristotle",
        "socrates",
        "philosophy",
        "filsafat",
        "republic",
        "ethics",
        "metaphysics",
        "guénon",
        "traditionalism",
        # Religious/Spiritual texts
        "zohar",
        "kabbalah",
        "mahabharata",
        "ramayana",
        "bhagavad gita",
        "rumi",
        "sufi",
        "dante",
        "divine comedy",
        # Indonesian Culture
        "geertz",
        "religion of java",
        "kartini",
        "anderson",
        "imagined communities",
        "javanese culture",
        "indonesian culture",
        # Computer Science
        "sicp",
        "design patterns",
        "code complete",
        "programming",
        "software engineering",
        "algorithms",
        "data structures",
        "recursion",
        "functional programming",
        "lambda calculus",
        "oop",
        # Machine Learning
        "machine learning",
        "deep learning",
        "neural networks",
        "ml",
        "ai theory",
        "probabilistic",
        "murphy",
        "goodfellow",
        # Literature
        "shakespeare",
        "homer",
        "iliad",
        "odyssey",
        "literature",
    ]

    # Phase 3: Smart Fallback Chains
    # Define fallback priority for each primary collection
    # Format: primary_collection -> [fallback1, fallback2, fallback3]
    FALLBACK_CHAINS = {
        "visa_oracle": ["legal_architect", "tax_genius", "property_knowledge"],
        "kbli_eye": ["legal_architect", "tax_genius", "visa_oracle"],
        "kbli_comprehensive": ["kbli_eye", "legal_architect", "tax_genius"],
        "tax_genius": [
            "tax_knowledge",
            "tax_updates",
            "legal_architect",
        ],  # NEW: Tax Genius fallback chain
        "tax_knowledge": ["tax_genius", "tax_updates", "legal_architect"],
        "tax_updates": ["tax_genius", "tax_knowledge", "legal_updates"],
        "legal_architect": ["legal_updates", "kbli_eye", "tax_genius"],
        "legal_updates": ["legal_architect", "tax_updates", "visa_oracle"],
        "property_knowledge": ["property_listings", "legal_architect", "visa_oracle"],
        "property_listings": ["property_knowledge", "legal_architect", "tax_knowledge"],
        "zantara_books": ["visa_oracle"],  # Books is standalone, default fallback
        "bali_zero_team": [
            "visa_oracle",
            "legal_architect",
            "kbli_eye",
        ],  # Team fallback to main company collections
    }

    # Confidence thresholds (from centralized constants)
    CONFIDENCE_THRESHOLD_HIGH = RoutingConstants.CONFIDENCE_THRESHOLD_HIGH
    CONFIDENCE_THRESHOLD_LOW = RoutingConstants.CONFIDENCE_THRESHOLD_LOW

    def __init__(self):
        """Initialize the router with fallback chain support"""
        logger.info("QueryRouter initialized (Phase 3: Smart Fallback Chain Agent enabled)")

        # Initialize sub-services
        self.keyword_matcher = KeywordMatcherService()
        self.confidence_calculator = ConfidenceCalculatorService()
        self.fallback_manager = FallbackManagerService()
        self.priority_override = PriorityOverrideService()
        self.routing_stats = RoutingStatsService()

        # Backward compatibility: expose constants
        self.CONFIDENCE_THRESHOLD_HIGH = RoutingConstants.CONFIDENCE_THRESHOLD_HIGH
        self.CONFIDENCE_THRESHOLD_LOW = RoutingConstants.CONFIDENCE_THRESHOLD_LOW
        self.FALLBACK_CHAINS = self.fallback_manager.FALLBACK_CHAINS

        # Backward compatibility: expose keyword lists
        self.VISA_KEYWORDS = self.keyword_matcher.domain_keywords["visa"]
        self.KBLI_KEYWORDS = self.keyword_matcher.domain_keywords["kbli"]
        self.TAX_KEYWORDS = self.keyword_matcher.domain_keywords["tax"]
        self.LEGAL_KEYWORDS = self.keyword_matcher.domain_keywords["legal"]
        self.PROPERTY_KEYWORDS = self.keyword_matcher.domain_keywords["property"]
        self.TEAM_KEYWORDS = self.keyword_matcher.domain_keywords["team"]
        self.BOOKS_KEYWORDS = self.keyword_matcher.domain_keywords["books"]
        self.UPDATE_KEYWORDS = self.keyword_matcher.modifier_keywords["updates"]
        self.TAX_GENIUS_KEYWORDS = self.keyword_matcher.modifier_keywords["tax_genius"]
        self.BACKEND_SERVICES_KEYWORDS = self.priority_override.backend_services_keywords

        # Backward compatibility: expose stats dict
        self.fallback_stats = self.routing_stats.fallback_stats

    def _calculate_domain_scores(self, query: str) -> dict[str, int]:
        """
        Calculate domain scores for all domains (shared by route() and route_with_confidence()).

        REFACTORED: Delegates to KeywordMatcherService.

        Args:
            query: User query text

        Returns:
            Dictionary mapping domain names to scores
        """
        return self.keyword_matcher.calculate_domain_scores(query)

    def _check_priority_overrides(self, query: str) -> CollectionName | None:
        """
        Check for priority override patterns (identity, team, founder, backend services).

        REFACTORED: Delegates to PriorityOverrideService.

        Args:
            query: User query text

        Returns:
            Collection name if override detected, None otherwise
        """
        return self.priority_override.check_priority_overrides(query)

    def _determine_collection(self, domain_scores: dict[str, int], query: str) -> CollectionName:
        """
        Determine collection from domain scores (shared logic).

        Args:
            domain_scores: Dictionary of domain scores
            query: User query text (for modifier detection)

        Returns:
            Collection name
        """
        query_lower = query.lower()

        # Calculate modifier scores
        update_score = sum(1 for kw in self.UPDATE_KEYWORDS if kw in query_lower)
        tax_genius_score = sum(1 for kw in self.TAX_GENIUS_KEYWORDS if kw in query_lower)

        primary_domain = max(domain_scores, key=domain_scores.get)
        primary_score = domain_scores[primary_domain]

        # Debug logging
        logger.debug(f"Domain scores: {domain_scores}")

        # Intelligent sub-routing based on primary domain + modifiers
        if primary_score == 0:
            # No matches - default to legal_unified (Cloud Reality)
            collection = "legal_unified"
            logger.info(f"🧭 Route: {collection} (default - no keyword matches)")
        elif primary_domain == "tax":
            # Tax domain: route to tax_genius (Unified in Cloud)
            collection = "tax_genius"
            logger.info(f"🧭 Route: {collection} (tax unified: tax={domain_scores['tax']})")
        elif primary_domain == "legal":
            # Legal domain: route to legal_unified
            collection = "legal_unified"
            logger.info(f"🧭 Route: {collection} (legal unified: legal={domain_scores['legal']})")
        elif primary_domain == "property":
            # Property domain: route to property_unified
            collection = "property_unified"
            logger.info(
                f"🧭 Route: {collection} (property unified: property={domain_scores['property']})"
            )
        elif primary_domain == "visa":
            collection = "visa_oracle"
            logger.info(f"🧭 Route: {collection} (visa: score={domain_scores['visa']})")
        elif primary_domain == "kbli":
            collection = "kbli_unified"
            logger.info(f"🧭 Route: {collection} (kbli: score={domain_scores['kbli']})")
        elif primary_domain == "team":
            collection = "bali_zero_team"
            logger.info(f"🧭 Route: {collection} (team: score={domain_scores['team']})")
        else:  # books
            # Fallback for books if collection missing
            collection = "visa_oracle"
            logger.info(f"🧭 Route: {collection} (books fallback: score={domain_scores['books']})")

        return collection

    async def route_query(self, query: str, user_id: str | None = None) -> dict[str, Any]:
        """
        Route query to appropriate collection (for test compatibility).

        Args:
            query: User query text
            user_id: Optional user ID

        Returns:
            Dictionary with collection_name and metadata
        """
        collection = self.route(query)
        result = self.route_with_confidence(query, return_fallbacks=True)
        # route_with_confidence returns (collection, confidence, fallbacks)
        if isinstance(result, tuple) and len(result) == 3:
            _, confidence, fallbacks = result
        else:
            # Fallback if signature changed
            confidence = 1.0
            fallbacks = []
        return {
            "collection_name": collection,
            "confidence": confidence,
            "fallbacks": fallbacks,
        }

    def route(self, query: str) -> CollectionName:
        """
        Route query to appropriate collection (9-way intelligent routing - Phase 2).

        REFACTORED: Uses shared helper methods to avoid code duplication.

        Args:
            query: User query text

        Returns:
            Collection name from 9 available collections
        """
        # Check priority overrides first
        override = self._check_priority_overrides(query)
        if override:
            return override

        # Calculate domain scores
        domain_scores = self._calculate_domain_scores(query)

        # Determine collection
        return self._determine_collection(domain_scores, query)

    def calculate_confidence(self, query: str, domain_scores: dict) -> float:
        """
        Calculate confidence score for routing decision (Phase 3).

        REFACTORED: Delegates to ConfidenceCalculatorService.

        Args:
            query: User query text
            domain_scores: Dictionary of domain scores from routing

        Returns:
            Confidence score between 0.0 and 1.0
        """
        return self.confidence_calculator.calculate_confidence(query, domain_scores)

    def get_fallback_collections(
        self, primary_collection: CollectionName, confidence: float, max_fallbacks: int = 3
    ) -> list[CollectionName]:
        """
        Get list of collections to try based on confidence (Phase 3).

        REFACTORED: Delegates to FallbackManagerService.

        Args:
            primary_collection: Initially routed collection
            confidence: Confidence score (0.0 - 1.0)
            max_fallbacks: Maximum fallbacks to return

        Returns:
            List of collections to query in order (primary first)
        """
        return self.fallback_manager.get_fallback_collections(
            primary_collection, confidence, max_fallbacks
        )

    def route_with_confidence(
        self, query: str, return_fallbacks: bool = True
    ) -> tuple[CollectionName, float, list[CollectionName]]:
        """
        Route query with confidence scoring and fallback suggestions (Phase 3).

        REFACTORED: Uses shared helper methods to avoid code duplication.

        This is the enhanced routing method that returns detailed routing information.
        Use this when you need to query multiple collections based on confidence.

        Args:
            query: User query text
            return_fallbacks: If True, include fallback collections in result

        Returns:
            Tuple of:
            - primary_collection: Best matching collection
            - confidence: Confidence score (0.0 - 1.0)
            - fallback_collections: List of all collections to try (primary + fallbacks)
        """
        # Check priority overrides first
        override = self._check_priority_overrides(query)
        if override:
            return (override, 1.0, [override])

        # Calculate domain scores (shared method)
        domain_scores = self._calculate_domain_scores(query)

        # Determine collection (shared method)
        collection = self._determine_collection(domain_scores, query)

        # Calculate confidence
        confidence = self.calculate_confidence(query, domain_scores)

        # Get fallback collections
        if return_fallbacks:
            all_collections = self.get_fallback_collections(collection, confidence)
        else:
            all_collections = [collection]

        # Update stats (delegated to RoutingStatsService)
        self.routing_stats.record_route(
            confidence=confidence,
            fallbacks_used=len(all_collections) > 1,
            confidence_threshold_high=self.CONFIDENCE_THRESHOLD_HIGH,
            confidence_threshold_low=self.CONFIDENCE_THRESHOLD_LOW,
        )

        # Logging
        if len(all_collections) > 1:
            logger.info(
                f"🎯 Route with fallbacks: {collection} (confidence={confidence:.2f}) "
                f"→ fallbacks={all_collections[1:]}"
            )
        else:
            logger.info(f"🎯 Route: {collection} (confidence={confidence:.2f}, high confidence)")

        return collection, confidence, all_collections

    def get_routing_stats(self, query: str) -> dict:
        """
        Get detailed routing analysis for debugging (Phase 2: extended with Oracle domains).

        REFACTORED: Uses shared helper methods.

        Args:
            query: User query text

        Returns:
            Dictionary with routing analysis including all domain scores
        """
        query_lower = query.lower()

        # Calculate all domain scores (use shared method)
        domain_scores = self._calculate_domain_scores(query)

        # Calculate modifier scores (delegated to KeywordMatcherService)
        modifier_scores = self.keyword_matcher.get_modifier_scores(query)
        update_score = modifier_scores.get("updates", 0)
        tax_genius_score = modifier_scores.get("tax_genius", 0)

        # Find matching keywords (delegated to KeywordMatcherService)
        visa_matches = self.keyword_matcher.get_matched_keywords(query, "visa")
        kbli_matches = self.keyword_matcher.get_matched_keywords(query, "kbli")
        tax_matches = self.keyword_matcher.get_matched_keywords(query, "tax")
        legal_matches = self.keyword_matcher.get_matched_keywords(query, "legal")
        property_matches = self.keyword_matcher.get_matched_keywords(query, "property")
        books_matches = self.keyword_matcher.get_matched_keywords(query, "books")
        update_matches = [kw for kw in self.UPDATE_KEYWORDS if kw in query.lower()]

        collection = self.route(query)

        return {
            "query": query,
            "selected_collection": collection,
            "domain_scores": domain_scores,
            "modifier_scores": {"updates": update_score, "tax_genius": tax_genius_score},
            "matched_keywords": {
                "visa": visa_matches,
                "kbli": kbli_matches,
                "tax": tax_matches,
                "legal": legal_matches,
                "property": property_matches,
                "books": books_matches,
                "updates": update_matches,
            },
            "routing_method": "keyword_layer_1_phase_2",
            "total_matches": sum(domain_scores.values()),
        }

    def get_fallback_stats(self) -> dict:
        """
        Get statistics about fallback chain usage (Phase 3).

        REFACTORED: Delegates to RoutingStatsService.

        Returns:
            Dictionary with fallback metrics
        """
        return self.routing_stats.get_fallback_stats()
