"""Tests for CRAG (Conditional Retrieval-Augmented Generation) Router.

# Organo: backend-rag/rag → produce CRAGDecision → consuma da orchestrator_core
"""

from __future__ import annotations

import pytest

from backend.services.rag.agentic.query_plan import (
    KGStrategy,
    QueryComplexity,
    QueryDomain,
    QueryPlan,
)
from backend.services.rag.crag_router import CRAGDecision, CRAGRouter


class TestCRAGRouterPhase1:
    """Phase 1: Pre-retrieval routing based on QueryPlan."""

    def setup_method(self) -> None:
        self.router = CRAGRouter(
            enable_hyde=True,
            enable_nlm_orchestrator=True,
            enable_deep_research=True,
        )

    def _plan(self, **kwargs: object) -> QueryPlan:
        defaults = {"query": "test query"}
        defaults.update(kwargs)
        return QueryPlan(**defaults)  # type: ignore[arg-type]

    # ── Greeting shortcut ──

    def test_greeting_skips_rag(self) -> None:
        plan = self._plan(domain=QueryDomain.GREETING, skip_rag=True)
        decision = self.router.route(plan)
        assert decision.skip_rag is True
        assert decision.use_qdrant is False

    # ── Simple queries ──

    def test_simple_query_qdrant_only(self) -> None:
        plan = self._plan(
            domain=QueryDomain.GENERAL,
            complexity=QueryComplexity.SIMPLE,
            kg_strategy=KGStrategy.NONE,
        )
        decision = self.router.route(plan)
        assert decision.use_qdrant is True
        assert decision.use_kg is False
        assert decision.use_hyde is False
        assert decision.use_reranker is False
        assert decision.use_nlm_verify is False

    # ── Lookup queries ──

    def test_lookup_with_kg_entity(self) -> None:
        plan = self._plan(
            domain=QueryDomain.VISA,
            complexity=QueryComplexity.LOOKUP,
            kg_strategy=KGStrategy.ENTITY_LOOKUP,
        )
        decision = self.router.route(plan)
        assert decision.use_qdrant is True
        assert decision.use_kg is True
        assert decision.use_reranker is False

    # ── Multi-hop queries ──

    def test_multi_hop_enables_reranker(self) -> None:
        plan = self._plan(
            domain=QueryDomain.VISA,
            complexity=QueryComplexity.MULTI_HOP,
            kg_strategy=KGStrategy.SUBGRAPH,
            enable_hyde=True,
        )
        decision = self.router.route(plan)
        assert decision.use_reranker is True
        assert decision.use_kg is True
        assert decision.use_hyde is True  # enable_hyde=True on plan + router

    def test_multi_hop_critical_domain_triggers_nlm(self) -> None:
        plan = self._plan(
            domain=QueryDomain.VISA,
            complexity=QueryComplexity.MULTI_HOP,
            kg_strategy=KGStrategy.SUBGRAPH,
        )
        decision = self.router.route(plan)
        assert decision.use_nlm_verify is True

    def test_multi_hop_non_critical_no_nlm(self) -> None:
        plan = self._plan(
            domain=QueryDomain.NEWS,
            complexity=QueryComplexity.MULTI_HOP,
            kg_strategy=KGStrategy.NONE,
        )
        decision = self.router.route(plan)
        assert decision.use_nlm_verify is False

    # ── Cross-domain queries ──

    def test_cross_domain_full_pipeline(self) -> None:
        plan = self._plan(
            domain=QueryDomain.VISA,
            complexity=QueryComplexity.CROSS_DOMAIN,
            kg_strategy=KGStrategy.FULL_TRAVERSAL,
        )
        decision = self.router.route(plan)
        assert decision.use_reranker is True
        assert decision.use_hyde is True
        assert decision.use_nlm_orchestrator is True
        assert decision.model_tier == "PRO"

    def test_cross_domain_without_nlm_orchestrator(self) -> None:
        router = CRAGRouter(enable_nlm_orchestrator=False, enable_hyde=True)
        plan = self._plan(
            domain=QueryDomain.TAX,
            complexity=QueryComplexity.CROSS_DOMAIN,
            kg_strategy=KGStrategy.FULL_TRAVERSAL,
        )
        decision = router.route(plan)
        assert decision.use_nlm_orchestrator is False
        assert decision.use_nlm_verify is True  # fallback to verify

    # ── Feature flags ──

    def test_hyde_disabled_by_router(self) -> None:
        router = CRAGRouter(enable_hyde=False)
        plan = self._plan(
            domain=QueryDomain.VISA,
            complexity=QueryComplexity.MULTI_HOP,
            kg_strategy=KGStrategy.SUBGRAPH,
            enable_hyde=True,
        )
        decision = router.route(plan)
        assert decision.use_hyde is False

    def test_collections_copied_from_plan(self) -> None:
        plan = self._plan(
            domain=QueryDomain.VISA,
            collections=["visa_oracle", "legal_unified_hybrid"],
        )
        decision = self.router.route(plan)
        assert decision.collections == ["visa_oracle", "legal_unified_hybrid"]


class TestCRAGRouterPhase2:
    """Phase 2: Post-retrieval refinement based on evidence score."""

    def setup_method(self) -> None:
        self.router = CRAGRouter(
            enable_hyde=True,
            enable_deep_research=True,
        )

    # ── Low confidence triggers ──

    def test_very_low_confidence_triggers_deep_research(self) -> None:
        decision = CRAGDecision(use_qdrant=True)
        refined = self.router.refine_after_retrieval(decision, retrieval_score=0.10)
        assert refined.use_deep_research is True

    def test_low_confidence_triggers_hyde(self) -> None:
        decision = CRAGDecision(use_qdrant=True, use_hyde=False)
        refined = self.router.refine_after_retrieval(
            decision, retrieval_score=0.30, self_rag_threshold=0.4
        )
        assert refined.use_hyde is True

    def test_low_confidence_no_hyde_if_already_active(self) -> None:
        decision = CRAGDecision(use_qdrant=True, use_hyde=True)
        refined = self.router.refine_after_retrieval(
            decision, retrieval_score=0.30, self_rag_threshold=0.4
        )
        assert refined.use_hyde is True  # unchanged

    # ── High confidence downgrades ──

    def test_high_confidence_disables_nlm_verify(self) -> None:
        decision = CRAGDecision(use_nlm_verify=True)
        refined = self.router.refine_after_retrieval(decision, retrieval_score=0.80)
        assert refined.use_nlm_verify is False

    def test_skip_rag_unchanged(self) -> None:
        decision = CRAGDecision(skip_rag=True)
        refined = self.router.refine_after_retrieval(decision, retrieval_score=0.05)
        assert refined.use_deep_research is False  # skip_rag → no changes

    # ── Feature flags ──

    def test_deep_research_disabled_by_flag(self) -> None:
        router = CRAGRouter(enable_deep_research=False)
        decision = CRAGDecision(use_qdrant=True)
        refined = router.refine_after_retrieval(decision, retrieval_score=0.05)
        assert refined.use_deep_research is False

    def test_hyde_disabled_by_flag(self) -> None:
        router = CRAGRouter(enable_hyde=False)
        decision = CRAGDecision(use_qdrant=True, use_hyde=False)
        refined = router.refine_after_retrieval(decision, retrieval_score=0.30)
        assert refined.use_hyde is False
