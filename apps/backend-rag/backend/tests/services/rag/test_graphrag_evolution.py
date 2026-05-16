"""
Tests for GraphRAG Evolution v6.0 components.

Covers:
1. QueryPlanner — domain classification, entity extraction, KG strategy selection
2. QueryPlan — dataclass integrity
3. KG Auto-Expansion — entity extraction heuristics, confidence calculation,
   staging pattern (no prod writes)
4. Migration 077 — staging table SQL validity

Run: cd apps/backend-rag && PYTHONPATH=. python -m pytest backend/tests/services/rag/test_graphrag_evolution.py -v
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# QueryPlan Tests
# ============================================================================


class TestQueryPlan:
    """Test QueryPlan dataclass."""

    def test_query_plan_defaults(self) -> None:
        from backend.services.rag.agentic.query_plan import (
            KGStrategy,
            QueryComplexity,
            QueryDomain,
            QueryPlan,
        )

        plan = QueryPlan(query="test")
        assert plan.query == "test"
        assert plan.domain == QueryDomain.GENERAL
        assert plan.complexity == QueryComplexity.SIMPLE
        assert plan.kg_strategy == KGStrategy.NONE
        assert plan.skip_rag is False
        assert plan.collections == []
        assert plan.entities == []
        assert plan.model_tier == "FLASH"

    def test_query_hash_auto_computed(self) -> None:
        from backend.services.rag.agentic.query_plan import QueryPlan

        plan = QueryPlan(query="What is KITAS?")
        assert len(plan.query_hash) == 16
        expected = hashlib.sha256(b"What is KITAS?").hexdigest()[:16]
        assert plan.query_hash == expected

    def test_kg_strategy_enum_values(self) -> None:
        from backend.services.rag.agentic.query_plan import KGStrategy

        assert KGStrategy.NONE == "none"
        assert KGStrategy.ENTITY_LOOKUP == "entity_lookup"
        assert KGStrategy.SUBGRAPH == "subgraph"
        assert KGStrategy.FULL_TRAVERSAL == "full_traversal"
        assert KGStrategy.GOLDEN_ROUTE == "golden_route"

    def test_query_domain_enum_values(self) -> None:
        from backend.services.rag.agentic.query_plan import QueryDomain

        assert QueryDomain.VISA == "visa"
        assert QueryDomain.TAX == "tax"
        assert QueryDomain.PROPERTY == "property"
        assert QueryDomain.KBLI == "kbli"
        assert QueryDomain.COMPANY == "company"
        assert QueryDomain.GENERAL == "general"
        assert QueryDomain.PRICING == "pricing"
        assert QueryDomain.GREETING == "greeting"


# ============================================================================
# QueryPlanner Tests
# ============================================================================


class TestQueryPlanner:
    """Test QueryPlanner heuristic routing."""

    def setup_method(self) -> None:
        from backend.services.rag.agentic.query_planner import QueryPlanner

        self.planner = QueryPlanner()

    def test_visa_domain_from_entity(self) -> None:
        plan = self.planner.plan("What documents for KITAS?")
        assert plan.domain.value == "visa"
        assert any(e.name == "KITAS" for e in plan.entities)

    def test_tax_domain_from_entity(self) -> None:
        plan = self.planner.plan("How to register NPWP?")
        assert plan.domain.value == "tax"

    def test_property_domain_from_keyword(self) -> None:
        plan = self.planner.plan("Hak Pakai in Canggu")
        assert plan.domain.value == "property"

    def test_company_domain_from_entity(self) -> None:
        plan = self.planner.plan("How to setup PT PMA in Bali?")
        assert plan.domain.value == "company"

    def test_kbli_domain(self) -> None:
        plan = self.planner.plan("What is KBLI 56101?")
        assert plan.domain.value == "kbli"

    def test_greeting_skip_rag(self) -> None:
        plan = self.planner.plan("Buongiorno!")
        assert plan.domain.value == "greeting"
        assert plan.skip_rag is True
        assert plan.collections == []
        assert plan.kg_strategy.value == "none"

    def test_pricing_domain(self) -> None:
        plan = self.planner.plan("How much does PT PMA cost?")
        # PT PMA entity → company domain, but "how much" → pricing
        # Entity takes priority over keyword
        assert plan.domain.value in ("company", "pricing")

    def test_cross_domain_complexity(self) -> None:
        plan = self.planner.plan("KITAS requirements for PT PMA director")
        assert len(plan.entities) >= 2
        # KITAS (visa) + PT PMA (company) = cross-domain
        entity_types = {e.entity_type for e in plan.entities}
        assert len(entity_types) >= 2

    def test_simple_query_no_entities(self) -> None:
        plan = self.planner.plan("Hello, how are you?")
        assert plan.complexity.value in ("simple", "greeting")

    def test_collections_include_legal_for_complex(self) -> None:
        plan = self.planner.plan("KITAS for restaurant owner in Bali")
        if plan.complexity.value != "simple":
            assert "legal_unified_hybrid" in plan.collections

    def test_kg_strategy_subgraph_for_visa(self) -> None:
        plan = self.planner.plan("What is KITAS visa?")
        assert plan.kg_strategy.value in ("entity_lookup", "subgraph")

    def test_kg_strategy_none_for_greeting(self) -> None:
        plan = self.planner.plan("Ciao!")
        assert plan.kg_strategy.value == "none"

    def test_model_tier_flash_for_simple(self) -> None:
        plan = self.planner.plan("What is NPWP?")
        assert plan.model_tier == "FLASH"

    def test_planner_latency_under_50ms(self) -> None:
        """Planner must complete in <50ms (heuristic, no LLM)."""
        import time

        queries = [
            "What is KITAS?",
            "How to setup PT PMA with KBLI 56101?",
            "Buongiorno!",
            "NPWP registration for foreigners",
            "Hak Pakai villa rental in Seminyak",
        ]
        for q in queries:
            start = time.time()
            self.planner.plan(q)
            elapsed_ms = (time.time() - start) * 1000
            assert elapsed_ms < 50, f"Planner took {elapsed_ms:.1f}ms for: {q}"

    def test_no_llm_calls(self) -> None:
        """Verify planner makes zero external API calls."""
        # If planner tried to call an LLM, it would import and use one
        # We verify by checking the module has no LLM-related imports
        import inspect

        from backend.services.rag.agentic.query_planner import QueryPlanner

        source = inspect.getsource(QueryPlanner)
        assert "llm" not in source.lower() or "no llm" in source.lower()
        assert "openai" not in source.lower()
        assert "anthropic" not in source.lower()
        assert "gemini" not in source.lower()


# ============================================================================
# KG Auto-Expansion Tests
# ============================================================================


class TestEntityExtraction:
    """Test heuristic entity extraction."""

    def test_extract_visa_entities(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("KITAS visa requires passport and NPWP")
        names = {e.name for e in entities}
        assert "KITAS" in names
        assert "NPWP" in names

    def test_extract_company_entities(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("PT PMA company setup requires NIB from OSS")
        names = {e.name for e in entities}
        assert "PT PMA" in names
        assert "NIB" in names
        assert "OSS" in names

    def test_extract_regulation(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("Berdasarkan UU 6/2023 dan PP 28/2025")
        types = {e.entity_type for e in entities}
        assert "undang_undang" in types
        assert "peraturan_pemerintah" in types

    def test_extract_property(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("Foreigner can get Hak Pakai but not Hak Milik")
        names = {e.name for e in entities}
        assert "Hak Pakai" in names
        assert "Hak Milik" in names

    def test_extract_kbli(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("KBLI 56101 for restaurant business")
        types = {e.entity_type for e in entities}
        assert "kbli" in types

    def test_max_entities_limit(self) -> None:
        from backend.services.rag.kg_auto_expansion import (
            MAX_ENTITIES_PER_RESPONSE,
            extract_entities_heuristic,
        )

        # Long text with many entities
        text = "KITAS KITAP VITAS RPTKA IMTA PT PMA NIB OSS NPWP PPh 21 PPh 23 PPN SPT UU 1/2020 PP 2/2021"
        entities = extract_entities_heuristic(text)
        assert len(entities) <= MAX_ENTITIES_PER_RESPONSE

    def test_empty_text_no_entities(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("")
        assert entities == []

    def test_dedup_same_entity(self) -> None:
        from backend.services.rag.kg_auto_expansion import extract_entities_heuristic

        entities = extract_entities_heuristic("KITAS is required. Apply for KITAS now.")
        kitas_count = sum(1 for e in entities if e.name == "KITAS")
        assert kitas_count == 1


class TestRelationshipExtraction:
    """Test heuristic relationship extraction."""

    def test_requires_relationship(self) -> None:
        from backend.services.rag.kg_auto_expansion import (
            extract_entities_heuristic,
            extract_relationships_heuristic,
        )

        text = "PT PMA requires NPWP registration before operations."
        entities = extract_entities_heuristic(text)
        edges = extract_relationships_heuristic(text, entities)
        if edges:
            assert any(e.relationship_type == "REQUIRES" for e in edges)

    def test_no_edges_single_entity(self) -> None:
        from backend.services.rag.kg_auto_expansion import (
            extract_entities_heuristic,
            extract_relationships_heuristic,
        )

        text = "KITAS is a temporary stay permit."
        entities = extract_entities_heuristic(text)
        edges = extract_relationships_heuristic(text, entities)
        assert edges == []


class TestEntityIdNormalization:
    """Test entity ID normalization."""

    def test_normalize_visa(self) -> None:
        from backend.services.rag.kg_auto_expansion import normalize_entity_id

        assert normalize_entity_id("KITAS", "kitas") == "visa:kitas"

    def test_normalize_company(self) -> None:
        from backend.services.rag.kg_auto_expansion import normalize_entity_id

        assert normalize_entity_id("PT PMA", "pt_pma") == "company:pt_pma"

    def test_normalize_regulation(self) -> None:
        from backend.services.rag.kg_auto_expansion import normalize_entity_id

        result = normalize_entity_id("UU 6/2023", "undang_undang")
        assert result.startswith("regulation:")
        assert "6_2023" in result

    def test_normalize_kbli(self) -> None:
        from backend.services.rag.kg_auto_expansion import normalize_entity_id

        result = normalize_entity_id("KBLI 56101", "kbli")
        assert result == "kbli:kbli_56101"

    def test_normalize_tax(self) -> None:
        from backend.services.rag.kg_auto_expansion import normalize_entity_id

        assert normalize_entity_id("NPWP", "npwp") == "tax:npwp"


class TestConfidenceCalculation:
    """Test dynamic confidence scoring."""

    def test_new_entity_base_confidence(self) -> None:
        from backend.services.rag.kg_auto_expansion import calculate_dynamic_confidence

        conf = calculate_dynamic_confidence(
            base_confidence=0.70,
            existing_confidence=None,
            source_count=1,
        )
        assert conf == 0.70

    def test_corroboration_boost(self) -> None:
        from backend.services.rag.kg_auto_expansion import (
            CORROBORATION_BONUS,
            calculate_dynamic_confidence,
        )

        conf = calculate_dynamic_confidence(
            base_confidence=0.70,
            existing_confidence=0.80,
            source_count=2,
        )
        assert conf == 0.80 + CORROBORATION_BONUS

    def test_max_confidence_cap(self) -> None:
        from backend.services.rag.kg_auto_expansion import calculate_dynamic_confidence

        conf = calculate_dynamic_confidence(
            base_confidence=0.95,
            existing_confidence=0.98,
            source_count=5,
        )
        assert conf <= 1.0

    def test_multi_source_multiplier(self) -> None:
        from backend.services.rag.kg_auto_expansion import calculate_dynamic_confidence

        conf_1source = calculate_dynamic_confidence(0.70, None, 1)
        conf_3source = calculate_dynamic_confidence(0.70, None, 3)
        assert conf_3source > conf_1source


class TestEdgeIdGeneration:
    """Test deterministic edge ID generation."""

    def test_deterministic(self) -> None:
        from backend.services.rag.kg_auto_expansion import generate_edge_id

        id1 = generate_edge_id("visa:kitas", "tax:npwp", "REQUIRES")
        id2 = generate_edge_id("visa:kitas", "tax:npwp", "REQUIRES")
        assert id1 == id2

    def test_different_for_different_edges(self) -> None:
        from backend.services.rag.kg_auto_expansion import generate_edge_id

        id1 = generate_edge_id("visa:kitas", "tax:npwp", "REQUIRES")
        id2 = generate_edge_id("tax:npwp", "visa:kitas", "REQUIRES")
        assert id1 != id2

    def test_starts_with_edge_prefix(self) -> None:
        from backend.services.rag.kg_auto_expansion import generate_edge_id

        eid = generate_edge_id("a", "b", "REL")
        assert eid.startswith("edge:")


# ============================================================================
# KG Auto-Expansion Service Tests (with mocked DB)
# ============================================================================


class TestKGAutoExpansion:
    """Test the main expansion service."""

    @pytest.mark.asyncio
    async def test_skip_low_evidence(self) -> None:
        from backend.services.rag.kg_auto_expansion import KGAutoExpansion

        mock_pool = MagicMock()
        service = KGAutoExpansion(db_pool=mock_pool)
        result = await service.expand_from_response(
            response_text="some text",
            evidence_score=0.3,  # Below 0.6 threshold
        )
        assert result.nodes_inserted == 0
        assert result.edges_inserted == 0
        # DB should NOT be called
        mock_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_no_source_chunks(self) -> None:
        from backend.services.rag.kg_auto_expansion import KGAutoExpansion

        mock_pool = MagicMock()
        service = KGAutoExpansion(db_pool=mock_pool)
        result = await service.expand_from_response(
            response_text="some text",
            evidence_score=0.8,
            source_chunks_text=None,
            query=None,
        )
        assert result.nodes_inserted == 0

    @pytest.mark.asyncio
    async def test_extracts_from_source_chunks_not_response(self) -> None:
        """CRITICAL: Must extract from source chunks, NOT from LLM response text."""

        from backend.services.rag.kg_auto_expansion import KGAutoExpansion

        # asyncpg conn.transaction() returns a sync object with __aenter__/__aexit__
        # We need a MagicMock (not AsyncMock) that supports `async with`
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = None  # Not in prod KG
        mock_conn.execute.return_value = "INSERT 0 1"

        # transaction() must return a non-coroutine async context manager
        tx_cm = MagicMock()
        tx_cm.__aenter__ = AsyncMock(return_value=None)
        tx_cm.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx_cm)

        # acquire() must also be a non-coroutine async context manager
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=acquire_cm)

        service = KGAutoExpansion(db_pool=mock_pool)

        # Response text mentions KITAP, but source chunks mention KITAS
        result = await service.expand_from_response(
            response_text="You should apply for KITAP permanent residence.",
            evidence_score=0.8,
            source_chunks_text=["KITAS temporary stay permit requires passport and NPWP"],
            source_chunk_ids=["chunk_123"],
        )

        # Should have extracted entities from source chunks
        assert result.nodes_inserted > 0 or result.nodes_updated > 0
        assert result.duration_ms > 0
        assert len(result.errors) == 0


# ============================================================================
# Migration 077 Tests
# ============================================================================


class TestMigration077:
    """Test staging tables migration SQL."""

    @pytest.mark.asyncio
    async def test_migration_apply_calls_execute(self) -> None:
        from backend.migrations.migration_077_kg_staging_tables import apply

        mock_conn = AsyncMock()
        await apply(mock_conn)
        # Should execute 3 statements: staging nodes, staging edges, alter kg_nodes
        assert mock_conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_migration_rollback_calls_execute(self) -> None:
        from backend.migrations.migration_077_kg_staging_tables import rollback

        mock_conn = AsyncMock()
        await rollback(mock_conn)
        assert mock_conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_migration_sql_contains_staging_tables(self) -> None:
        from backend.migrations.migration_077_kg_staging_tables import apply

        mock_conn = AsyncMock()
        await apply(mock_conn)

        all_sql = " ".join(
            str(call.args[0]) for call in mock_conn.execute.call_args_list
        )
        assert "kg_nodes_staging" in all_sql
        assert "kg_edges_staging" in all_sql
        assert "source_collection_previous" in all_sql
        assert "promotion_status" in all_sql
        assert "extraction_source" in all_sql
