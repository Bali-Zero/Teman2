"""Tests for Self-RAG Reflection Loop in LangGraph."""
import pytest
from backend.app.agents.graph import (
    create_rag_graph,
    check_hallucination_node,
    transform_query_node,
    should_reflect_or_end,
    MAX_REFLECTION_RETRIES,
)


class TestSelfRAGGraph:
    def test_graph_compiles_with_reflection_nodes(self):
        graph = create_rag_graph()
        node_names = list(graph.nodes.keys())
        assert "check_hallucination" in node_names
        assert "transform_query" in node_names

    def test_graph_has_six_nodes(self):
        graph = create_rag_graph()
        # __start__, retrieve, grade, generate, check_hallucination, transform_query
        assert len(graph.nodes) == 6


class TestCheckHallucination:
    @pytest.mark.asyncio
    async def test_passes_with_grounded_generation(self):
        state = {
            "generation": "The KITAS visa requires a passport valid for 18 months",
            "filtered_documents": [{"content": "KITAS visa passport valid 18 months requirement"}],
            "execution_path": [],
            "reflection_retries": 0,
        }
        result = await check_hallucination_node(state)
        assert result["hallucination_check"] == "passed"
        assert result["grounding_score"] > 0.05

    @pytest.mark.asyncio
    async def test_fails_with_ungrounded_generation(self):
        state = {
            "generation": "completely unrelated text about cooking recipes",
            "filtered_documents": [{"content": "KITAS visa immigration Indonesia permit"}],
            "execution_path": [],
            "reflection_retries": 0,
        }
        result = await check_hallucination_node(state)
        assert result["hallucination_check"] == "failed"

    @pytest.mark.asyncio
    async def test_skips_when_max_retries(self):
        state = {
            "generation": "test",
            "filtered_documents": [{"content": "doc"}],
            "execution_path": [],
            "reflection_retries": MAX_REFLECTION_RETRIES,
        }
        result = await check_hallucination_node(state)
        assert result["hallucination_check"] == "skipped"

    @pytest.mark.asyncio
    async def test_skips_without_generation(self):
        state = {
            "generation": "",
            "filtered_documents": [],
            "execution_path": [],
            "reflection_retries": 0,
        }
        result = await check_hallucination_node(state)
        assert result["hallucination_check"] == "skipped"


class TestTransformQuery:
    @pytest.mark.asyncio
    async def test_increments_retry_counter(self):
        state = {
            "question": "original question",
            "filtered_documents": [{"content": "some context"}],
            "execution_path": [],
            "reflection_retries": 0,
        }
        result = await transform_query_node(state)
        assert result["reflection_retries"] == 1

    @pytest.mark.asyncio
    async def test_transforms_query(self):
        state = {
            "question": "KITAS requirements",
            "filtered_documents": [{"content": "work permit Indonesia"}],
            "execution_path": [],
            "reflection_retries": 0,
        }
        result = await transform_query_node(state)
        assert result["question"] != "KITAS requirements"


class TestShouldReflectOrEnd:
    def test_retry_on_failed_check(self):
        state = {"hallucination_check": "failed", "reflection_retries": 0}
        assert should_reflect_or_end(state) == "transform_query"

    def test_end_on_passed_check(self):
        state = {"hallucination_check": "passed", "reflection_retries": 0}
        result = should_reflect_or_end(state)
        assert result == "__end__"

    def test_end_when_max_retries(self):
        state = {"hallucination_check": "failed", "reflection_retries": MAX_REFLECTION_RETRIES}
        result = should_reflect_or_end(state)
        assert result == "__end__"
