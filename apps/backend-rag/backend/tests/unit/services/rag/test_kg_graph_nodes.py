"""
Unit tests for backend/services/rag/kg_graph_nodes.py

Covers:
- _detect_domain_from_query()
- _is_non_kbli_entity()
- _get_entity_type_filter()
- format_chains_for_llm()
- extract_evidence_from_chains()
- calculate_workflow_confidence()
- understand_query_node() (LLM success, LLM failure, JSON parse error)
- resolve_entities_node() (cache hit, exact match, fuzzy match, miss)
- traverse_graph_node() (cache hit, BFS traversal, empty frontier)
- reason_over_graph_node() (with chains, empty chains)
- synthesize_workflow_node() (with chains, empty chains)
"""

import asyncio
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.kg_graph_nodes import (
    _detect_domain_from_query,
    _get_entity_type_filter,
    _is_non_kbli_entity,
    calculate_workflow_confidence,
    extract_evidence_from_chains,
    format_chains_for_llm,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper: build a minimal KGAgentState dict
# ============================================================================
def _make_state(**overrides: Any) -> dict[str, Any]:
    """Create a minimal KGAgentState-like dict with defaults."""
    base: dict[str, Any] = {
        "query": "test query",
        "user_context": {},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "reasoning_steps": [],
        "confidence_scores": {},
        "intent": None,
        "extracted_entities": [],
        "domain": None,
        "workflow": None,
        "answer_evidence": [],
        "golden_route_match": None,
        "messages": [],
        "next_step": "",
    }
    base.update(overrides)
    return base


# ============================================================================
# _detect_domain_from_query
# ============================================================================
class TestDetectDomainFromQuery:
    """Tests for fast domain detection without LLM."""

    def test_visa_kitas(self) -> None:
        result = _detect_domain_from_query("what is kitas?")
        assert result["domain"] == "visa"
        assert result["intent"] == "visa"
        assert "KITAS" in result["entities"]

    def test_visa_kitap(self) -> None:
        result = _detect_domain_from_query("how to get kitap")
        assert result["domain"] == "visa"
        assert "KITAP" in result["entities"]

    def test_visa_vitas(self) -> None:
        result = _detect_domain_from_query("vitas application process")
        assert result["domain"] == "visa"
        assert "VITAS" in result["entities"]

    def test_visa_generic(self) -> None:
        result = _detect_domain_from_query("work permit for foreign worker")
        assert result["domain"] == "visa"

    def test_tax_npwp(self) -> None:
        result = _detect_domain_from_query("how to register npwp")
        assert result["domain"] == "tax"
        assert "NPWP" in result["entities"]

    def test_tax_pph(self) -> None:
        result = _detect_domain_from_query("pph 21 calculation")
        assert result["domain"] == "tax"
        assert "PPh" in result["entities"]

    def test_tax_ppn(self) -> None:
        result = _detect_domain_from_query("ppn for services")
        assert result["domain"] == "tax"
        assert "PPN" in result["entities"]

    def test_property_hak_pakai(self) -> None:
        result = _detect_domain_from_query("hak pakai for foreigners")
        assert result["domain"] == "property"
        assert "Hak Pakai" in result["entities"]

    def test_property_hgb(self) -> None:
        result = _detect_domain_from_query("hgb certificate process")
        assert result["domain"] == "property"
        assert "HGB" in result["entities"]

    def test_general_query(self) -> None:
        result = _detect_domain_from_query("how to start a business")
        assert result["domain"] == "general"

    def test_evisa(self) -> None:
        result = _detect_domain_from_query("e-visa application")
        assert result["domain"] == "visa"

    def test_immigration(self) -> None:
        result = _detect_domain_from_query("immigration office bali")
        assert result["domain"] == "visa"


# ============================================================================
# _is_non_kbli_entity
# ============================================================================
class TestIsNonKbliEntity:
    """Tests for entity classification as non-KBLI."""

    def test_kitas_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("KITAS") is True

    def test_npwp_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("NPWP") is True

    def test_hak_pakai_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("hak_pakai") is True

    def test_kbli_code_is_not_non_kbli(self) -> None:
        assert _is_non_kbli_entity("56101") is False

    def test_generic_entity_is_not_non_kbli(self) -> None:
        assert _is_non_kbli_entity("Restaurant") is False

    def test_explicit_type_visa_type(self) -> None:
        assert _is_non_kbli_entity("E28A", entity_type="visa_type") is True

    def test_explicit_type_tax_concept(self) -> None:
        assert _is_non_kbli_entity("PPh21", entity_type="tax_concept") is True

    def test_imta_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("IMTA") is True

    def test_rptka_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("RPTKA") is True

    def test_hgb_is_non_kbli(self) -> None:
        assert _is_non_kbli_entity("HGB") is True


# ============================================================================
# _get_entity_type_filter
# ============================================================================
class TestGetEntityTypeFilter:
    """Tests for entity type filter resolution."""

    def test_kitas_returns_visa_types(self) -> None:
        result = _get_entity_type_filter("KITAS")
        assert result is not None
        assert "visa" in result

    def test_npwp_returns_tax_types(self) -> None:
        result = _get_entity_type_filter("NPWP")
        assert result is not None
        assert "tax" in result

    def test_hak_pakai_returns_property_types(self) -> None:
        result = _get_entity_type_filter("hak_pakai")
        assert result is not None
        assert "property" in result

    def test_5digit_number_returns_kbli_types(self) -> None:
        result = _get_entity_type_filter("56101")
        assert result is not None
        assert "kbli" in result

    def test_generic_returns_none(self) -> None:
        assert _get_entity_type_filter("Restaurant") is None

    def test_4digit_number_returns_none(self) -> None:
        assert _get_entity_type_filter("5610") is None


# ============================================================================
# format_chains_for_llm
# ============================================================================
class TestFormatChainsForLlm:
    """Tests for LLM context formatting."""

    def test_empty_chains(self) -> None:
        result = format_chains_for_llm([])
        assert "No graph chains found" in result

    def test_single_chain(self) -> None:
        chains = [[{
            "source_name": "KBLI 56101",
            "source_type": "kbli",
            "relationship_type": "REQUIRES",
            "target_name": "PT PMA",
            "target_type": "company",
        }]]
        result = format_chains_for_llm(chains)
        assert "Chain 1:" in result
        assert "KBLI 56101" in result
        assert "REQUIRES" in result
        assert "PT PMA" in result

    def test_multiple_chains_truncated_at_10(self) -> None:
        chains = [[{
            "source_name": f"Entity{i}",
            "source_type": "type",
            "relationship_type": "REQUIRES",
            "target_name": f"Target{i}",
            "target_type": "type",
        }] for i in range(15)]
        result = format_chains_for_llm(chains)
        assert "Chain 10:" in result
        assert "Chain 11:" not in result


# ============================================================================
# extract_evidence_from_chains
# ============================================================================
class TestExtractEvidenceFromChains:
    """Tests for evidence extraction."""

    def test_empty_chains(self) -> None:
        assert extract_evidence_from_chains([]) == []

    def test_extracts_unique_entities(self) -> None:
        chains = [
            [{
                "target_entity_id": "e1",
                "target_name": "PT PMA",
                "target_type": "company",
                "relationship_type": "REQUIRES",
                "source_name": "KBLI",
            }],
            [{
                "target_entity_id": "e1",  # duplicate
                "target_name": "PT PMA",
                "target_type": "company",
                "relationship_type": "ENABLES",
                "source_name": "NIB",
            }],
            [{
                "target_entity_id": "e2",
                "target_name": "KITAS",
                "target_type": "visa",
                "relationship_type": "REQUIRES",
                "source_name": "PT PMA",
            }],
        ]
        evidence = extract_evidence_from_chains(chains)
        assert len(evidence) == 2  # e1 deduplicated
        ids = {e["entity_id"] for e in evidence}
        assert ids == {"e1", "e2"}


# ============================================================================
# calculate_workflow_confidence (deprecated, kept for compat)
# ============================================================================
class TestCalculateWorkflowConfidence:
    """Tests for deprecated confidence calculation."""

    def test_no_chains(self) -> None:
        state = _make_state(relationship_chains=[])
        assert calculate_workflow_confidence(state) == 0.0

    def test_few_chains(self) -> None:
        state = _make_state(relationship_chains=[["a"], ["b"]])
        conf = calculate_workflow_confidence(state)
        assert 0.0 < conf <= 1.0

    def test_many_chains(self) -> None:
        state = _make_state(relationship_chains=[["a"]] * 12)
        conf = calculate_workflow_confidence(state)
        assert conf >= 0.7

    def test_with_confidence_scores(self) -> None:
        state = _make_state(
            relationship_chains=[["a"]] * 5,
            confidence_scores={"e1": 0.9, "e2": 0.85},
        )
        conf = calculate_workflow_confidence(state)
        assert conf > 0.5

    def test_clear_intent_boost(self) -> None:
        state_general = _make_state(
            relationship_chains=[["a"]] * 5,
            intent="general",
        )
        state_visa = _make_state(
            relationship_chains=[["a"]] * 5,
            intent="visa",
        )
        conf_general = calculate_workflow_confidence(state_general)
        conf_visa = calculate_workflow_confidence(state_visa)
        assert conf_visa >= conf_general


# ============================================================================
# understand_query_node
# ============================================================================
class TestUnderstandQueryNode:
    """Tests for the query understanding LangGraph node."""

    @staticmethod
    def _structured_llm(parsed_obj: Any | None = None,
                        *, side_effect: Any | None = None) -> AsyncMock:
        """Build an LLM mock compatible with PR #382 structured-output API.

        `understand_query_node` calls `llm.with_structured_output(QueryIntentSchema)`
        and then `.ainvoke(...)` on the wrapper. The wrapper returns a Pydantic
        instance directly (NOT a `.content` JSON string). This helper wires both
        layers so tests stay readable.
        """
        structured_llm = AsyncMock()
        if side_effect is not None:
            structured_llm.ainvoke = AsyncMock(side_effect=side_effect)
        else:
            structured_llm.ainvoke = AsyncMock(return_value=parsed_obj)

        llm = MagicMock()
        llm.with_structured_output = MagicMock(return_value=structured_llm)
        return llm

    @pytest.mark.asyncio
    async def test_successful_llm_parse(self) -> None:
        from backend.services.rag.kg_graph_nodes import (
            QueryIntentSchema,
            understand_query_node,
        )

        state = _make_state(query="What is KITAS?")
        llm = self._structured_llm(QueryIntentSchema(
            intent="visa", domain="visa", entities=["KITAS"], citizenship="foreign",
        ))

        result = await understand_query_node(state, llm)
        assert result["intent"] == "visa"
        assert result["domain"] == "visa"
        assert "KITAS" in result["extracted_entities"]
        assert result["user_context"]["citizenship"] == "foreign"

    @pytest.mark.asyncio
    async def test_llm_timeout_fallback(self) -> None:
        from backend.services.rag.kg_graph_nodes import understand_query_node

        state = _make_state(query="kitas application")
        llm = self._structured_llm(side_effect=asyncio.TimeoutError())

        result = await understand_query_node(state, llm)
        # Should fall back to domain detection
        assert result["domain"] == "visa"

    @pytest.mark.asyncio
    async def test_llm_json_parse_error_fallback(self) -> None:
        from backend.services.rag.kg_graph_nodes import understand_query_node
        from pydantic import ValidationError

        # Simulate the structured-output parser raising ValidationError when
        # the upstream LLM returns malformed JSON. The node catches it and
        # falls back to fast-path domain detection.
        state = _make_state(query="npwp registration")
        try:
            from backend.services.rag.kg_graph_nodes import QueryIntentSchema
            QueryIntentSchema(intent="x")  # missing required fields
        except ValidationError as ve:
            llm = self._structured_llm(side_effect=ve)
        else:
            pytest.skip("schema no longer raises on minimal input")

        result = await understand_query_node(state, llm)
        assert result["domain"] == "tax"  # fallback from domain detection

    @pytest.mark.asyncio
    async def test_general_query(self) -> None:
        from backend.services.rag.kg_graph_nodes import (
            QueryIntentSchema,
            understand_query_node,
        )

        state = _make_state(query="how to start business in bali")
        llm = self._structured_llm(QueryIntentSchema(
            intent="company_setup", domain="company", entities=["PT PMA"],
        ))

        result = await understand_query_node(state, llm)
        assert result["intent"] == "company_setup"


# ============================================================================
# resolve_entities_node
# ============================================================================
class TestResolveEntitiesNode:
    """Tests for entity resolution node."""

    @pytest.mark.asyncio
    async def test_empty_entities(self) -> None:
        from backend.services.rag.kg_graph_nodes import resolve_entities_node

        state = _make_state(extracted_entities=[])
        db_pool = AsyncMock()

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache_fn.return_value = mock_cache
            result = await resolve_entities_node(state, db_pool)
        assert result["current_entities"] == []

    @pytest.mark.asyncio
    async def test_non_kbli_entity_skipped(self) -> None:
        from backend.services.rag.kg_graph_nodes import resolve_entities_node

        state = _make_state(extracted_entities=["KITAS"])
        db_pool = AsyncMock()

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_resolved_entity = AsyncMock(return_value=None)
            mock_cache_fn.return_value = mock_cache
            result = await resolve_entities_node(state, db_pool)
        assert result["current_entities"] == []

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        from backend.services.rag.kg_graph_nodes import resolve_entities_node

        state = _make_state(extracted_entities=["56101"])
        db_pool = AsyncMock()

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_resolved_entity = AsyncMock(
                return_value={"entity_id": "kbli:56101", "confidence": 0.95},
            )
            mock_cache_fn.return_value = mock_cache
            result = await resolve_entities_node(state, db_pool)
        assert "kbli:56101" in result["current_entities"]
        assert result["confidence_scores"]["kbli:56101"] == 0.95

    @pytest.mark.asyncio
    async def test_exact_match(self) -> None:
        from backend.services.rag.kg_graph_nodes import resolve_entities_node

        state = _make_state(extracted_entities=["56101"])
        mock_conn = AsyncMock()

        # Simulate record behavior
        mock_row = {"entity_id": "kbli:56101", "name": "56101", "confidence": 0.9, "entity_type": "kbli"}
        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        db_pool = AsyncMock()
        db_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_resolved_entity = AsyncMock(return_value=None)
            mock_cache.set_resolved_entity = AsyncMock()
            mock_cache_fn.return_value = mock_cache
            result = await resolve_entities_node(state, db_pool)
        assert "kbli:56101" in result["current_entities"]


# ============================================================================
# traverse_graph_node
# ============================================================================
class TestTraverseGraphNode:
    """Tests for the graph traversal node."""

    @pytest.mark.asyncio
    async def test_no_starting_entities(self) -> None:
        from backend.services.rag.kg_graph_nodes import traverse_graph_node

        state = _make_state(current_entities=[])
        db_pool = AsyncMock()
        result = await traverse_graph_node(state, db_pool)
        assert result["relationship_chains"] == []

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        from backend.services.rag.kg_graph_nodes import traverse_graph_node

        cached_chains = [[{
            "source_entity_id": "a",
            "target_entity_id": "b",
            "relationship_type": "REQUIRES",
        }]]
        state = _make_state(current_entities=["a"])

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_traversal = AsyncMock(return_value=cached_chains)
            mock_cache_fn.return_value = mock_cache
            result = await traverse_graph_node(state, AsyncMock())
        assert len(result["relationship_chains"]) == 1
        assert "a" in result["visited_entities"]
        assert "b" in result["visited_entities"]

    @pytest.mark.asyncio
    async def test_bfs_traversal(self) -> None:
        from backend.services.rag.kg_graph_nodes import traverse_graph_node

        state = _make_state(current_entities=["node_a"])

        mock_edge = {
            "source_entity_id": "node_a",
            "source_name": "Node A",
            "source_type": "kbli",
            "relationship_type": "REQUIRES",
            "target_entity_id": "node_b",
            "target_name": "Node B",
            "target_type": "company",
            "target_confidence": 0.9,
            "edge_confidence": 0.85,
            "edge_source_collection": "col1",
            "target_source_collection": "col2",
            "target_created_at": None,
            "edge_created_at": None,
        }
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[[mock_edge], []])

        db_pool = AsyncMock()
        db_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("backend.services.rag.kg_cache.get_kg_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_traversal = AsyncMock(return_value=None)
            mock_cache.set_traversal = AsyncMock()
            mock_cache_fn.return_value = mock_cache
            result = await traverse_graph_node(state, db_pool, max_depth=2)

        assert len(result["relationship_chains"]) == 1
        assert result["relationship_chains"][0][0]["target_entity_id"] == "node_b"
        assert "node_a" in result["visited_entities"]
        assert "node_b" in result["visited_entities"]


# ============================================================================
# reason_over_graph_node
# ============================================================================
class TestReasonOverGraphNode:
    """Tests for LLM reasoning node."""

    @pytest.mark.asyncio
    async def test_no_chains_skips_reasoning(self) -> None:
        from backend.services.rag.kg_graph_nodes import reason_over_graph_node

        state = _make_state(relationship_chains=[], reasoning_steps=[])
        llm = AsyncMock()
        result = await reason_over_graph_node(state, llm)
        assert len(result["reasoning_steps"]) == 1
        assert "No graph evidence" in result["reasoning_steps"][0]
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_chains(self) -> None:
        from backend.services.rag.kg_graph_nodes import reason_over_graph_node

        chains = [[{
            "source_entity_id": "a",
            "source_name": "KBLI 56101",
            "source_type": "kbli",
            "relationship_type": "REQUIRES",
            "target_entity_id": "b",
            "target_name": "PT PMA",
            "target_type": "company",
        }]]
        state = _make_state(
            query="What do I need for a restaurant?",
            relationship_chains=chains,
            reasoning_steps=[],
            answer_evidence=[],
        )

        llm = AsyncMock()
        llm_response = MagicMock()
        llm_response.content = "Based on the graph, you need PT PMA for KBLI 56101."
        llm.ainvoke = AsyncMock(return_value=llm_response)

        result = await reason_over_graph_node(state, llm)
        assert len(result["reasoning_steps"]) == 1
        assert len(result["answer_evidence"]) == 1


# ============================================================================
# synthesize_workflow_node
# ============================================================================
class TestSynthesizeWorkflowNode:
    """Tests for workflow synthesis node."""

    @pytest.mark.asyncio
    async def test_no_chains_returns_none_workflow(self) -> None:
        from backend.services.rag.kg_graph_nodes import synthesize_workflow_node

        state = _make_state(relationship_chains=[], intent="visa")
        db_pool = AsyncMock()
        result = await synthesize_workflow_node(state, db_pool)
        assert result["workflow"] is None

    @pytest.mark.asyncio
    async def test_with_chains_builds_workflow(self) -> None:
        from backend.services.rag.kg_graph_nodes import synthesize_workflow_node

        chains = [
            [{
                "source_entity_id": "a",
                "target_entity_id": "b",
                "target_name": "PT PMA",
                "target_type": "company",
                "relationship_type": "REQUIRES",
                "depth": 1,
            }],
            [{
                "source_entity_id": "b",
                "target_entity_id": "c",
                "target_name": "NIB",
                "target_type": "document",
                "relationship_type": "ENABLES",
                "depth": 2,
            }],
        ]
        state = _make_state(
            relationship_chains=chains,
            intent="company_setup",
            confidence_scores={"b": 0.9, "c": 0.85},
        )

        with patch("backend.services.rag.confidence.calculate_dynamic_confidence") as mock_conf:
            from backend.services.rag.confidence import ConfidenceBreakdown
            mock_conf.return_value = ConfidenceBreakdown(overall=0.82)
            db_pool = AsyncMock()
            result = await synthesize_workflow_node(state, db_pool)

        wf = result["workflow"]
        assert wf is not None
        assert wf["type"] == "company_setup"
        assert len(wf["steps"]) == 2
        # Steps sorted by depth
        assert wf["steps"][0]["title"] == "PT PMA"
        assert wf["steps"][1]["title"] == "NIB"
        assert wf["confidence"] == 0.82
