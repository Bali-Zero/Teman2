"""CRAG (Conditional Retrieval-Augmented Generation) Router.

Decides which retrieval tiers to activate based on query classification
and post-retrieval confidence. Replaces scattered ad-hoc routing logic.

Two-phase routing:
  1. route()                   — pre-retrieval, based on QueryPlan
  2. refine_after_retrieval()  — post-retrieval, upgrades/downgrades tiers

References:
  Yan et al. 2024 — "Corrective Retrieval Augmented Generation"

# Organo: backend-rag/rag → produce CRAGDecision → consuma da orchestrator_core
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.services.rag.agentic.query_plan import (
    KGStrategy,
    QueryComplexity,
    QueryDomain,
    QueryPlan,
)

logger = logging.getLogger(__name__)

# Evidence thresholds (matching existing constants)
EVIDENCE_ABSTAIN = 0.15
EVIDENCE_CAUTIOUS_HIGH = 0.60
EVIDENCE_CONFIDENT = 0.70

# Critical domains that warrant NLM verification
CRITICAL_DOMAINS: frozenset[str] = frozenset({
    "visa", "tax", "legal", "immigration", "company", "property",
})


@dataclass
class CRAGDecision:
    """Output of CRAG Router — which tiers to activate for this query."""

    use_qdrant: bool = True
    use_kg: bool = False
    use_hyde: bool = False
    use_reranker: bool = False
    use_nlm_verify: bool = False
    use_nlm_orchestrator: bool = False
    use_deep_research: bool = False
    model_tier: str = "FLASH"
    skip_rag: bool = False
    kg_strategy: str = "none"
    collections: list[str] = field(default_factory=list)


class CRAGRouter:
    """Conditional routing based on query classification and retrieval confidence.

    Phase 1 (pre-retrieval): Deterministic routing from QueryPlan.
    Phase 2 (post-retrieval): Confidence-based tier upgrades/downgrades.
    """

    def __init__(
        self,
        enable_hyde: bool = False,
        enable_nlm_orchestrator: bool = False,
        enable_deep_research: bool = False,
    ) -> None:
        self._enable_hyde = enable_hyde
        self._enable_nlm_orchestrator = enable_nlm_orchestrator
        self._enable_deep_research = enable_deep_research

    def route(self, plan: QueryPlan) -> CRAGDecision:
        """Phase 1: Pre-retrieval routing based on QueryPlan.

        Deterministic, <1ms. Called before any search.
        """
        decision = CRAGDecision()

        # ── Greeting shortcut ──
        if plan.skip_rag or plan.domain == QueryDomain.GREETING:
            decision.skip_rag = True
            decision.use_qdrant = False
            logger.debug("CRAG: skip_rag (greeting/shortcut)")
            return decision

        # ── Copy plan metadata ──
        decision.collections = list(plan.collections)
        decision.model_tier = plan.model_tier
        decision.kg_strategy = plan.kg_strategy.value

        # ── KG routing ──
        if plan.kg_strategy != KGStrategy.NONE:
            decision.use_kg = True

        # ── Complexity-based decisions ──
        if plan.complexity == QueryComplexity.SIMPLE:
            # Simple queries: Qdrant only, minimal processing
            decision.use_reranker = False
            decision.use_hyde = False

        elif plan.complexity == QueryComplexity.LOOKUP:
            # Lookup: Qdrant + KG entity lookup, no extras
            decision.use_reranker = False

        elif plan.complexity == QueryComplexity.MULTI_HOP:
            # Multi-hop: full pipeline with reranker
            decision.use_reranker = True
            decision.use_hyde = self._enable_hyde and plan.enable_hyde

            # NLM verify for critical domains
            if plan.domain.value in CRITICAL_DOMAINS:
                decision.use_nlm_verify = True

        elif plan.complexity == QueryComplexity.CROSS_DOMAIN:
            # Cross-domain: everything enabled
            decision.use_reranker = True
            decision.use_hyde = self._enable_hyde
            decision.model_tier = "PRO"

            # Always NLM orchestrator for cross-domain if enabled
            if self._enable_nlm_orchestrator:
                decision.use_nlm_orchestrator = True
            elif plan.domain.value in CRITICAL_DOMAINS:
                decision.use_nlm_verify = True

        logger.info(
            "CRAG route: domain=%s complexity=%s → "
            "qdrant=%s kg=%s hyde=%s reranker=%s nlm=%s/%s deep_research=%s",
            plan.domain.value,
            plan.complexity.value,
            decision.use_qdrant,
            decision.use_kg,
            decision.use_hyde,
            decision.use_reranker,
            decision.use_nlm_verify,
            decision.use_nlm_orchestrator,
            decision.use_deep_research,
        )

        return decision

    def refine_after_retrieval(
        self,
        decision: CRAGDecision,
        retrieval_score: float,
        self_rag_threshold: float = 0.4,
    ) -> CRAGDecision:
        """Phase 2: Post-retrieval refinement based on evidence score.

        Upgrades or downgrades tier decisions based on actual retrieval quality.
        """
        if decision.skip_rag:
            return decision

        # ── Very low confidence → trigger deep research ──
        if retrieval_score < EVIDENCE_ABSTAIN and self._enable_deep_research:
            decision.use_deep_research = True
            logger.info(
                "CRAG refine: retrieval_score=%.2f < ABSTAIN → deep_research=True",
                retrieval_score,
            )

        # ── Low confidence → trigger HyDE if not already active ──
        elif retrieval_score < self_rag_threshold and not decision.use_hyde:
            if self._enable_hyde:
                decision.use_hyde = True
                logger.info(
                    "CRAG refine: retrieval_score=%.2f < threshold=%.2f → hyde=True",
                    retrieval_score,
                    self_rag_threshold,
                )

        # ── High confidence → downgrade NLM verify (unnecessary) ──
        elif retrieval_score > EVIDENCE_CONFIDENT:
            if decision.use_nlm_verify:
                decision.use_nlm_verify = False
                logger.debug(
                    "CRAG refine: retrieval_score=%.2f > CONFIDENT → nlm_verify=False",
                    retrieval_score,
                )

        return decision
