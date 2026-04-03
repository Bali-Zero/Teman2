"""
Query Plan — Structured Execution Plan for RAG Pipeline

Output of QueryPlanner — consumed by OrchestratorCore to coordinate
vector search, KG traversal, and LLM reasoning in a single pass.

Author: Nuzantara Team
Date: 2026-04-03
Reference: docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md §2
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class KGStrategy(str, Enum):
    """Strategy for Knowledge Graph usage in query processing."""

    NONE = "none"                        # Skip KG entirely
    ENTITY_LOOKUP = "entity_lookup"      # Just resolve entities (1 SQL query)
    SUBGRAPH = "subgraph"                # Run domain subgraph (company/visa/etc.)
    FULL_TRAVERSAL = "full_traversal"    # BFS multi-hop (complex queries)
    GOLDEN_ROUTE = "golden_route"        # Deterministic workflow path


class QueryComplexity(str, Enum):
    """Estimated complexity of the query."""

    SIMPLE = "simple"            # Greeting, small talk, single fact
    LOOKUP = "lookup"            # Single entity lookup (pricing, KBLI code)
    MULTI_HOP = "multi_hop"      # Requires graph traversal (KITAS for restaurant)
    CROSS_DOMAIN = "cross_domain"  # Multiple domains (PT PMA + KITAS + tax)


class QueryDomain(str, Enum):
    """Primary domain of the query."""

    VISA = "visa"
    TAX = "tax"
    PROPERTY = "property"
    KBLI = "kbli"
    COMPANY = "company"
    GENERAL = "general"
    PRICING = "pricing"
    NEWS = "news"
    GREETING = "greeting"


@dataclass
class ExtractedEntity:
    """A typed entity extracted from the query."""

    name: str
    entity_type: str
    confidence: float = 1.0


@dataclass
class QueryPlan:
    """
    Deterministic execution plan for a user query.

    Produced by QueryPlanner, consumed by OrchestratorCore.
    Replaces the fragmented routing through IntentClassifier +
    EntityExtractor + RoutingManager.

    Attributes:
        query: Original user query
        query_hash: SHA256 hash for caching/dedup
        domain: Primary domain classification
        entities: Typed entities with confidence
        complexity: Estimated query complexity
        collections: Qdrant collections to search (ordered by priority)
        kg_strategy: How to use the Knowledge Graph
        kg_subgraph: Which domain subgraph to invoke (if any)
        kg_max_depth: Max traversal depth for graph exploration
        model_tier: LLM model tier (FLASH/PRO/DEEP_THINK)
        enable_reranking: Whether to use CrossEncoder reranking
        skip_rag: Skip RAG pipeline entirely (greetings, etc.)
        kg_confidence_boost: Added to evidence score if KG path found
        min_evidence_threshold: Override default evidence threshold
        max_latency_ms: Timeout budget for this query type
        parallel_kg: Run KG in parallel with vector search
        prefetch_collections: Pre-fetch results for ReAct (skip tool call)
    """

    # Identity
    query: str
    query_hash: str = ""

    # Classification
    domain: QueryDomain = QueryDomain.GENERAL
    entities: list[ExtractedEntity] = field(default_factory=list)
    complexity: QueryComplexity = QueryComplexity.SIMPLE

    # Execution Plan
    collections: list[str] = field(default_factory=list)
    kg_strategy: KGStrategy = KGStrategy.NONE
    kg_subgraph: str | None = None
    kg_max_depth: int = 1
    model_tier: str = "FLASH"
    enable_reranking: bool = False
    skip_rag: bool = False

    # Confidence Modifiers
    kg_confidence_boost: float = 0.0
    min_evidence_threshold: float = 0.15

    # Performance Budget
    max_latency_ms: int = 5000
    parallel_kg: bool = True
    prefetch_collections: bool = True

    def __post_init__(self) -> None:
        """Compute query hash if not set."""
        if not self.query_hash:
            self.query_hash = hashlib.sha256(self.query.encode()).hexdigest()[:16]
