"""
Unified Query Planner

Replaces the fragmented routing through IntentClassifier + EntityExtractor +
RoutingManager with a single deterministic planner that produces a QueryPlan.

No LLM calls — pure heuristic/rule-based classification (<50ms).

The planner decides:
- Which Qdrant collections to query
- Whether KG traversal is needed (and which strategy)
- Which subgraph to invoke
- LLM model tier selection
- Confidence thresholds and latency budgets

Author: Nuzantara Team
Date: 2026-04-03
Reference: docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md §2
"""

import logging
import re
import time
from typing import Any

from backend.services.rag.agentic.query_plan import (
    ExtractedEntity,
    KGStrategy,
    QueryComplexity,
    QueryDomain,
    QueryPlan,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Domain Keyword Dictionaries
# ============================================================================

_VISA_KEYWORDS: frozenset[str] = frozenset({
    "kitas", "kitap", "vitas", "visa", "work permit", "rptka", "imta",
    "immigration", "imigrasi", "izin tinggal", "stay permit", "telex",
    "e28a", "e31a", "e33a", "e34a", "voa", "visa on arrival",
    "onshore", "offshore", "tka", "tenaga kerja asing",
})

_TAX_KEYWORDS: frozenset[str] = frozenset({
    "tax", "pph", "ppn", "npwp", "pajak", "tasse", "fiscal", "vat",
    "spt", "efin", "faktur pajak", "bukti potong", "withholding",
    "pbb", "bea materai", "tax compliance", "tax return",
})

_PROPERTY_KEYWORDS: frozenset[str] = frozenset({
    "property", "villa", "hak pakai", "hgb", "hak milik",
    "rental", "real estate", "land", "tanah", "zoning",
    "bphtb", "imb", "pbg", "slf", "sertifikat tanah",
    "balik nama", "akta jual beli", "ppat", "notaris",
})

_COMPANY_KEYWORDS: frozenset[str] = frozenset({
    "pt pma", "pt lokal", "perorangan", "cv", "company",
    "azienda", "società", "firma", "koperasi", "yayasan",
    "badan hukum", "company setup", "business formation",
    "nib", "oss", "izin usaha", "siup",
})

_KBLI_KEYWORDS: frozenset[str] = frozenset({
    "kbli", "business classification", "kode usaha",
    "klasifikasi", "sektor", "business activity",
})

_PRICING_KEYWORDS: frozenset[str] = frozenset({
    "how much", "quanto costa", "price", "prezzo", "costo",
    "berapa biaya", "berapa harga", "cost of", "tarif",
    "pricing", "fee", "budget",
})

_GREETING_KEYWORDS: frozenset[str] = frozenset({
    "hello", "hi", "hey", "ciao", "buongiorno", "buonasera",
    "good morning", "good afternoon", "halo", "selamat",
    "thanks", "thank you", "grazie", "terima kasih",
})

_NEWS_KEYWORDS: frozenset[str] = frozenset({
    "news", "latest", "update", "recent", "notizie",
    "regulation change", "new law", "perubahan",
})

# ============================================================================
# Entity Extraction Patterns
# ============================================================================

_ENTITY_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, entity_type, display_name_override or empty)
    (r"\bKITAS\b", "visa", "KITAS"),
    (r"\bKITAP\b", "visa", "KITAP"),
    (r"\bVITAS\b", "visa", "VITAS"),
    (r"\bRPTKA\b", "visa", "RPTKA"),
    (r"\bIMTA\b", "visa", "IMTA"),
    (r"\be(\d{2})[a-z]?\b", "visa", ""),  # E28A, E31A etc.
    (r"\bPT\s+PMA\b", "company", "PT PMA"),
    (r"\bPT\s+Perorangan\b", "company", "PT Perorangan"),
    (r"\bCV\b", "company", "CV"),
    (r"\bKBLI\s*(\d{5})\b", "kbli", ""),
    (r"\bNPWP\b", "tax", "NPWP"),
    (r"\bPPh\s*\d+\b", "tax", ""),
    (r"\bPPN\b", "tax", "PPN"),
    (r"\bSPT\b", "tax", "SPT"),
    (r"\bNIB\b", "permit", "NIB"),
    (r"\bOSS\b", "permit", "OSS"),
    (r"\bHak\s+Pakai\b", "property", "Hak Pakai"),
    (r"\bHGB\b", "property", "HGB"),
    (r"\bHak\s+Milik\b", "property", "Hak Milik"),
    (r"\bUU\s*(?:No\.?\s*)?\d+(?:/\d{4})?\b", "regulation", ""),
    (r"\bPP\s*(?:No\.?\s*)?\d+(?:/\d{4})?\b", "regulation", ""),
]

# ============================================================================
# Collection Routing Map
# ============================================================================

_DOMAIN_COLLECTIONS: dict[QueryDomain, list[str]] = {
    QueryDomain.VISA: ["visa_oracle", "legal_unified_hybrid"],
    QueryDomain.TAX: ["nuzantara_general_hybrid", "legal_unified_hybrid"],
    QueryDomain.PROPERTY: ["nuzantara_general_hybrid", "legal_unified_hybrid"],
    QueryDomain.KBLI: ["kbli_2025_final"],
    QueryDomain.COMPANY: ["legal_unified_hybrid", "kbli_2025_final"],
    QueryDomain.PRICING: ["nuzantara_general_hybrid"],
    QueryDomain.NEWS: ["balizero_news"],
    QueryDomain.GENERAL: ["legal_unified_hybrid", "training_conversations_hybrid"],
    QueryDomain.GREETING: [],
}

# ============================================================================
# Query Planner
# ============================================================================


class QueryPlanner:
    """
    Unified query planner — replaces IntentClassifier + EntityExtractor + RoutingManager.

    Pure heuristic, no LLM calls, <50ms latency.

    ROLLOUT: Runs in shadow mode (dual-run with legacy pipeline) for 2 weeks.
    Feature flag: USE_QUERY_PLANNER env var (default: false).
    Switch criteria: planner_match_rate > 92% for 7 consecutive days.

    Usage:
        >>> planner = QueryPlanner()
        >>> plan = planner.plan("What documents for KITAS?")
        >>> plan.domain, plan.collections, plan.kg_strategy
        visa ['visa_oracle', 'legal_unified_hybrid'] KGStrategy.SUBGRAPH
    """

    def plan(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
    ) -> QueryPlan:
        """
        Generate a deterministic execution plan for the query.

        Steps:
        1. Extract entities from query
        2. Classify domain based on entities + keywords
        3. Assess complexity
        4. Generate execution plan (collections, KG strategy, model tier)

        Args:
            query: User query string
            user_context: Optional user context (citizenship, session history)

        Returns:
            QueryPlan with all execution parameters
        """
        start = time.time()

        # Step 1: Extract entities
        entities = self._extract_entities(query)

        # Step 2: Classify domain
        domain = self._classify_domain(query, entities)

        # Step 3: Assess complexity
        complexity = self._assess_complexity(query, entities, domain)

        # Step 4: Build plan
        plan = QueryPlan(
            query=query,
            domain=domain,
            entities=entities,
            complexity=complexity,
        )

        # Execution parameters based on domain + complexity
        self._set_collections(plan)
        self._set_kg_strategy(plan)
        self._set_model_tier(plan)
        self._set_performance_budget(plan)

        # Greeting shortcut
        if domain == QueryDomain.GREETING:
            plan.skip_rag = True
            plan.collections = []
            plan.kg_strategy = KGStrategy.NONE

        elapsed_ms = (time.time() - start) * 1000
        logger.info(
            f"📋 [QueryPlanner] {elapsed_ms:.1f}ms → "
            f"domain={domain.value}, complexity={complexity.value}, "
            f"entities={len(entities)}, collections={plan.collections}, "
            f"kg={plan.kg_strategy.value}",
        )

        return plan

    # ================================================================
    # Step 1: Entity Extraction
    # ================================================================

    def _extract_entities(self, query: str) -> list[ExtractedEntity]:
        """Extract typed entities from query using regex patterns."""
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        for pattern, entity_type, display_name in _ENTITY_PATTERNS:
            for match in re.finditer(pattern, query, re.IGNORECASE):
                name = display_name or match.group(0).strip()
                key = f"{entity_type}:{name.lower()}"

                if key in seen:
                    continue
                seen.add(key)

                entities.append(
                    ExtractedEntity(
                        name=name,
                        entity_type=entity_type,
                        confidence=1.0,
                    ),
                )

        return entities

    # ================================================================
    # Step 2: Domain Classification
    # ================================================================

    def _classify_domain(
        self,
        query: str,
        entities: list[ExtractedEntity],
    ) -> QueryDomain:
        """
        Classify query domain based on entities and keywords.

        Priority: entity-based > keyword-based > general fallback.
        """
        query_lower = query.lower()

        # Entity-based classification (highest priority)
        entity_types = {e.entity_type for e in entities}

        if "visa" in entity_types:
            return QueryDomain.VISA
        if "tax" in entity_types:
            return QueryDomain.TAX
        if "property" in entity_types:
            return QueryDomain.PROPERTY
        if "kbli" in entity_types:
            return QueryDomain.KBLI
        if "company" in entity_types:
            return QueryDomain.COMPANY

        # Keyword-based classification
        scores: dict[QueryDomain, int] = {d: 0 for d in QueryDomain}

        for kw in _GREETING_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.GREETING] += 3  # High weight for greetings

        for kw in _PRICING_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.PRICING] += 2

        for kw in _VISA_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.VISA] += 1

        for kw in _TAX_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.TAX] += 1

        for kw in _PROPERTY_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.PROPERTY] += 1

        for kw in _COMPANY_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.COMPANY] += 1

        for kw in _KBLI_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.KBLI] += 1

        for kw in _NEWS_KEYWORDS:
            if kw in query_lower:
                scores[QueryDomain.NEWS] += 1

        # Pick highest scoring domain
        best_domain = max(scores, key=lambda d: scores[d])
        if scores[best_domain] > 0:
            return best_domain

        return QueryDomain.GENERAL

    # ================================================================
    # Step 3: Complexity Assessment
    # ================================================================

    def _assess_complexity(
        self,
        query: str,
        entities: list[ExtractedEntity],
        domain: QueryDomain,
    ) -> QueryComplexity:
        """
        Assess query complexity based on entities and structure.

        Rules:
        - 0 entities + greeting → SIMPLE
        - 1 entity + lookup pattern → LOOKUP
        - 2+ entities from same domain → MULTI_HOP
        - 2+ entities from different domains → CROSS_DOMAIN
        """
        if domain == QueryDomain.GREETING:
            return QueryComplexity.SIMPLE

        entity_count = len(entities)
        entity_types = {e.entity_type for e in entities}

        if entity_count == 0:
            # Check for complex patterns without explicit entities
            query_lower = query.lower()
            if " and " in query_lower or " e " in query_lower:
                return QueryComplexity.MULTI_HOP
            return QueryComplexity.SIMPLE

        if entity_count == 1:
            return QueryComplexity.LOOKUP

        # Multiple entities
        if len(entity_types) >= 2:
            return QueryComplexity.CROSS_DOMAIN

        return QueryComplexity.MULTI_HOP

    # ================================================================
    # Step 4a: Collection Selection
    # ================================================================

    def _set_collections(self, plan: QueryPlan) -> None:
        """Set Qdrant collections based on domain and entities."""
        plan.collections = list(_DOMAIN_COLLECTIONS.get(plan.domain, []))

        # Cross-domain: merge collections from all entity domains
        if plan.complexity == QueryComplexity.CROSS_DOMAIN:
            entity_domains = {
                self._entity_type_to_domain(e.entity_type) for e in plan.entities
            }
            for ed in entity_domains:
                for col in _DOMAIN_COLLECTIONS.get(ed, []):
                    if col not in plan.collections:
                        plan.collections.append(col)

        # Always include legal_unified_hybrid for non-trivial queries
        if (
            plan.complexity != QueryComplexity.SIMPLE
            and "legal_unified_hybrid" not in plan.collections
            and plan.domain not in (QueryDomain.GREETING, QueryDomain.PRICING, QueryDomain.NEWS)
        ):
            plan.collections.append("legal_unified_hybrid")

    def _entity_type_to_domain(self, entity_type: str) -> QueryDomain:
        """Map entity type to QueryDomain."""
        mapping = {
            "visa": QueryDomain.VISA,
            "tax": QueryDomain.TAX,
            "property": QueryDomain.PROPERTY,
            "kbli": QueryDomain.KBLI,
            "company": QueryDomain.COMPANY,
            "permit": QueryDomain.COMPANY,
            "regulation": QueryDomain.GENERAL,
        }
        return mapping.get(entity_type, QueryDomain.GENERAL)

    # ================================================================
    # Step 4b: KG Strategy Selection
    # ================================================================

    def _set_kg_strategy(self, plan: QueryPlan) -> None:
        """Set KG strategy based on domain and complexity."""
        if plan.skip_rag or plan.domain in (QueryDomain.GREETING, QueryDomain.NEWS):
            plan.kg_strategy = KGStrategy.NONE
            plan.kg_confidence_boost = 0.0
            return

        if plan.domain == QueryDomain.PRICING:
            # Pricing uses PricingTool, not KG
            plan.kg_strategy = KGStrategy.NONE
            return

        # Domain-specific subgraph routing
        subgraph_map = {
            QueryDomain.COMPANY: "company",
            QueryDomain.VISA: "visa",
            QueryDomain.PROPERTY: "property",
            QueryDomain.TAX: "tax",
            QueryDomain.KBLI: "company",  # KBLI routes through company subgraph
        }

        if plan.complexity == QueryComplexity.SIMPLE:
            plan.kg_strategy = KGStrategy.ENTITY_LOOKUP
            plan.kg_max_depth = 1
            plan.kg_confidence_boost = 0.05

        elif plan.complexity == QueryComplexity.LOOKUP:
            if plan.domain in subgraph_map:
                plan.kg_strategy = KGStrategy.SUBGRAPH
                plan.kg_subgraph = subgraph_map[plan.domain]
                plan.kg_max_depth = 1
                plan.kg_confidence_boost = 0.10
            else:
                plan.kg_strategy = KGStrategy.ENTITY_LOOKUP
                plan.kg_max_depth = 1
                plan.kg_confidence_boost = 0.05

        elif plan.complexity == QueryComplexity.MULTI_HOP:
            if plan.domain in subgraph_map:
                plan.kg_strategy = KGStrategy.SUBGRAPH
                plan.kg_subgraph = subgraph_map[plan.domain]
            else:
                plan.kg_strategy = KGStrategy.FULL_TRAVERSAL
            plan.kg_max_depth = 2
            plan.kg_confidence_boost = 0.15

        elif plan.complexity == QueryComplexity.CROSS_DOMAIN:
            plan.kg_strategy = KGStrategy.FULL_TRAVERSAL
            plan.kg_max_depth = 3
            plan.kg_confidence_boost = 0.20

    # ================================================================
    # Step 4c: Model Tier Selection
    # ================================================================

    def _set_model_tier(self, plan: QueryPlan) -> None:
        """Set LLM model tier based on complexity."""
        if plan.complexity in (QueryComplexity.SIMPLE, QueryComplexity.LOOKUP):
            plan.model_tier = "FLASH"
            plan.enable_reranking = False
        elif plan.complexity == QueryComplexity.MULTI_HOP:
            plan.model_tier = "FLASH"
            plan.enable_reranking = True
        elif plan.complexity == QueryComplexity.CROSS_DOMAIN:
            plan.model_tier = "PRO"
            plan.enable_reranking = True

    # ================================================================
    # Step 4d: Performance Budget
    # ================================================================

    def _set_performance_budget(self, plan: QueryPlan) -> None:
        """Set latency budget and parallel execution flags."""
        latency_map = {
            QueryComplexity.SIMPLE: 1000,
            QueryComplexity.LOOKUP: 3000,
            QueryComplexity.MULTI_HOP: 5000,
            QueryComplexity.CROSS_DOMAIN: 8000,
        }
        plan.max_latency_ms = latency_map.get(plan.complexity, 5000)

        # Pre-fetch for simple/lookup queries (skip ReAct tool call overhead)
        plan.prefetch_collections = plan.complexity in (
            QueryComplexity.SIMPLE,
            QueryComplexity.LOOKUP,
        )

        # Parallel KG for all non-simple queries
        plan.parallel_kg = plan.kg_strategy != KGStrategy.NONE
