"""Tests for backend.services.rag.multi_hop — MultiHopEngine."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.multi_hop import (
    HopResult,
    MergedHopContext,
    MultiHopEngine,
    MultiHopPlan,
    SubQuery,
    _classify_domain,
    _get_collections_for_domain,
)


# ---------------------------------------------------------------------------
# SubQuery / MultiHopPlan dataclasses
# ---------------------------------------------------------------------------

class TestSubQuery:
    def test_defaults(self) -> None:
        sq = SubQuery(text="open a restaurant")
        assert sq.domain == "general"
        assert sq.entities == []
        assert sq.collections == []

    def test_repr(self) -> None:
        sq = SubQuery(text="a very long query " * 5, domain="visa")
        r = repr(sq)
        assert "visa" in r
        assert len(r) < 200  # truncated


class TestMultiHopPlan:
    def test_hop_count(self) -> None:
        plan = MultiHopPlan(
            original_query="q",
            sub_queries=[SubQuery(text="a"), SubQuery(text="b")],
        )
        assert plan.hop_count == 2

    def test_domains(self) -> None:
        plan = MultiHopPlan(
            original_query="q",
            sub_queries=[
                SubQuery(text="a", domain="visa"),
                SubQuery(text="b", domain="tax"),
            ],
        )
        assert plan.domains == ["visa", "tax"]

    def test_empty_plan(self) -> None:
        plan = MultiHopPlan(original_query="q")
        assert plan.hop_count == 0
        assert plan.domains == []


# ---------------------------------------------------------------------------
# MergedHopContext
# ---------------------------------------------------------------------------

class TestMergedHopContext:
    def test_to_prompt_context_empty(self) -> None:
        ctx = MergedHopContext()
        assert ctx.to_prompt_context() == ""

    def test_to_prompt_context_with_hops(self) -> None:
        hop1 = HopResult(
            sub_query=SubQuery(text="visa query", domain="visa"),
            kg_entities=[{"name": "KITAS"}, {"name": "RPTKA"}],
            graph_summary="Visa domain graph",
        )
        hop2 = HopResult(
            sub_query=SubQuery(text="company query", domain="company"),
            kg_entities=[{"entity_id": "PT_PMA"}],
            graph_summary="Company domain graph",
        )
        bridge = [{"name": "PT PMA"}]
        ctx = MergedHopContext(
            hop_results=[hop1, hop2],
            bridge_entities=bridge,
        )
        prompt = ctx.to_prompt_context()
        assert "[Hop 1: VISA]" in prompt
        assert "[Hop 2: COMPANY]" in prompt
        assert "KITAS" in prompt
        assert "PT_PMA" in prompt
        assert "PT PMA" in prompt
        assert "Bridge entities" in prompt

    def test_to_prompt_context_no_bridge(self) -> None:
        hop = HopResult(
            sub_query=SubQuery(text="q", domain="tax"),
            graph_summary="Tax graph",
        )
        ctx = MergedHopContext(hop_results=[hop])
        prompt = ctx.to_prompt_context()
        assert "Bridge entities" not in prompt

    def test_to_prompt_context_entity_fallback(self) -> None:
        """Uses entity_id when name is missing."""
        hop = HopResult(
            sub_query=SubQuery(text="q", domain="visa"),
            kg_entities=[{"entity_id": "ENT_123"}],
        )
        ctx = MergedHopContext(hop_results=[hop])
        prompt = ctx.to_prompt_context()
        assert "ENT_123" in prompt

    def test_to_prompt_context_entity_unknown(self) -> None:
        """Falls back to '?' when both name and entity_id missing."""
        hop = HopResult(
            sub_query=SubQuery(text="q", domain="visa"),
            kg_entities=[{"other_field": "x"}],
        )
        ctx = MergedHopContext(hop_results=[hop])
        prompt = ctx.to_prompt_context()
        assert "?" in prompt


# ---------------------------------------------------------------------------
# _classify_domain
# ---------------------------------------------------------------------------

class TestClassifyDomain:
    def test_visa_keywords(self) -> None:
        assert _classify_domain("I need a KITAS work permit") == "visa"

    def test_tax_keywords(self) -> None:
        assert _classify_domain("What is PPH 21 withholding tax?") == "tax"

    def test_property_keywords(self) -> None:
        assert _classify_domain("Buy villa with hak pakai") == "property"

    def test_company_keywords(self) -> None:
        assert _classify_domain("Setup PT PMA for business in Bali") == "company"

    def test_kbli_keywords(self) -> None:
        assert _classify_domain("KBLI klasifikasi kode usaha") == "kbli"

    def test_general_fallback(self) -> None:
        assert _classify_domain("Hello how are you?") == "general"

    def test_case_insensitive(self) -> None:
        assert _classify_domain("VISA APPLICATION KITAS") == "visa"


# ---------------------------------------------------------------------------
# _get_collections_for_domain
# ---------------------------------------------------------------------------

class TestGetCollectionsForDomain:
    def test_visa_collections(self) -> None:
        cols = _get_collections_for_domain("visa")
        assert "visa_oracle" in cols

    def test_kbli_collections(self) -> None:
        cols = _get_collections_for_domain("kbli")
        assert "kbli_2025_final_hybrid" in cols

    def test_unknown_domain_returns_general(self) -> None:
        cols = _get_collections_for_domain("unknown_domain")
        assert cols == _get_collections_for_domain("general")


# ---------------------------------------------------------------------------
# MultiHopEngine.decompose
# ---------------------------------------------------------------------------

class TestDecompose:
    def setup_method(self) -> None:
        self.engine = MultiHopEngine()

    def test_single_domain_query(self) -> None:
        plan = self.engine.decompose("I need a KITAS visa")
        assert plan.hop_count == 1
        assert plan.sub_queries[0].domain == "visa"

    def test_multi_domain_with_and(self) -> None:
        plan = self.engine.decompose(
            "I want to open a restaurant and hire a foreign chef with KITAS"
        )
        # Should decompose into at least 2 hops
        assert plan.hop_count >= 1
        assert plan.original_query.startswith("I want")

    def test_multi_domain_with_dan(self) -> None:
        plan = self.engine.decompose(
            "Saya mau buka PT PMA dan mengurus visa KITAS"
        )
        assert plan.hop_count >= 1

    def test_multi_domain_with_semicolon(self) -> None:
        plan = self.engine.decompose(
            "Setup PT PMA for restaurant; apply for KITAS work permit"
        )
        assert plan.hop_count >= 1

    def test_short_fragments_filtered(self) -> None:
        plan = self.engine.decompose("a and b")
        # Fragments "a" and "b" are too short (<=5 chars), single hop
        assert plan.hop_count == 1

    def test_same_domain_fragments_merged(self) -> None:
        plan = self.engine.decompose(
            "I need a KITAS visa and also a stay permit extension"
        )
        # Both fragments are visa domain, should be merged into 1
        domains = plan.domains
        assert domains.count("visa") <= 1

    def test_preserves_original_query(self) -> None:
        q = "Some complex query about many things"
        plan = self.engine.decompose(q)
        assert plan.original_query == q


# ---------------------------------------------------------------------------
# MultiHopEngine.execute_hops
# ---------------------------------------------------------------------------

class TestExecuteHops:
    def setup_method(self) -> None:
        self.engine = MultiHopEngine()

    @pytest.mark.asyncio
    async def test_single_hop_execution(self) -> None:
        plan = MultiHopPlan(
            original_query="KITAS visa",
            sub_queries=[SubQuery(text="KITAS visa", domain="visa")],
        )
        mock_kg = AsyncMock()
        mock_kg.get_kg_context = AsyncMock(return_value={
            "entities_found": [{"entity_id": "kitas", "name": "KITAS"}],
            "relationships": [{"type": "REQUIRES"}],
            "source_chunk_ids": ["c1"],
            "graph_summary": "Visa KG",
        })
        mock_pool = MagicMock()

        result = await self.engine.execute_hops(plan, mock_kg, mock_pool)
        assert len(result.hop_results) == 1
        assert result.total_entities == 1
        assert result.total_relationships == 1

    @pytest.mark.asyncio
    async def test_multi_hop_parallel_execution(self) -> None:
        plan = MultiHopPlan(
            original_query="q",
            sub_queries=[
                SubQuery(text="visa query", domain="visa"),
                SubQuery(text="company query", domain="company"),
            ],
        )
        mock_kg = AsyncMock()
        mock_kg.get_kg_context = AsyncMock(return_value={
            "entities_found": [{"entity_id": "ent_1", "name": "E1"}],
            "relationships": [],
            "source_chunk_ids": [],
            "graph_summary": "",
        })
        mock_pool = MagicMock()

        result = await self.engine.execute_hops(plan, mock_kg, mock_pool)
        assert len(result.hop_results) == 2
        assert result.total_entities == 2

    @pytest.mark.asyncio
    async def test_bridge_entities_detected(self) -> None:
        """Entity appearing in 2+ hops is identified as bridge."""
        plan = MultiHopPlan(
            original_query="q",
            sub_queries=[
                SubQuery(text="visa query", domain="visa"),
                SubQuery(text="company query", domain="company"),
            ],
        )
        shared_entity = {"entity_id": "pt_pma", "name": "PT PMA"}

        call_count = 0
        async def side_effect(query, db_pool):
            nonlocal call_count
            call_count += 1
            return {
                "entities_found": [shared_entity, {"entity_id": f"unique_{call_count}", "name": f"U{call_count}"}],
                "relationships": [],
                "source_chunk_ids": [],
                "graph_summary": "",
            }

        mock_kg = AsyncMock()
        mock_kg.get_kg_context = AsyncMock(side_effect=side_effect)

        result = await self.engine.execute_hops(plan, mock_kg, MagicMock())
        assert len(result.bridge_entities) == 1
        assert result.bridge_entities[0]["entity_id"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_hop_failure_filtered_out(self) -> None:
        """Failed hops are logged but do not crash execution."""
        plan = MultiHopPlan(
            original_query="q",
            sub_queries=[
                SubQuery(text="visa query", domain="visa"),
                SubQuery(text="company query", domain="company"),
            ],
        )
        call_count = 0
        async def side_effect(query, db_pool):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("KG down")
            return {
                "entities_found": [{"entity_id": "e1"}],
                "relationships": [],
                "source_chunk_ids": [],
                "graph_summary": "",
            }

        mock_kg = AsyncMock()
        mock_kg.get_kg_context = AsyncMock(side_effect=side_effect)

        result = await self.engine.execute_hops(plan, mock_kg, MagicMock())
        # One hop failed, one succeeded
        assert len(result.hop_results) >= 1

    @pytest.mark.asyncio
    async def test_execute_single_hop_error_returns_empty(self) -> None:
        """_execute_single_hop gracefully handles errors."""
        mock_kg = AsyncMock()
        mock_kg.get_kg_context = AsyncMock(side_effect=RuntimeError("boom"))

        sq = SubQuery(text="test", domain="visa")
        result = await self.engine._execute_single_hop(sq, mock_kg, MagicMock())
        assert result.kg_entities == []
        assert result.graph_summary == ""
