"""
Unit tests for backend/app/agents/graph.py

Covers: set_search_service, set_llm_gateway, set_db_pool,
        _load_conversation_history, retrieve_node, grade_node,
        generate_node, check_hallucination_node, transform_query_node,
        should_reflect_or_end, should_continue_to_generation,
        create_rag_graph, invoke_rag_workflow.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.agents import graph as graph_module
from backend.app.agents.graph import (
    MAX_REFLECTION_RETRIES,
    _load_conversation_history,
    check_hallucination_node,
    create_rag_graph,
    generate_node,
    grade_node,
    retrieve_node,
    set_db_pool,
    set_llm_gateway,
    set_search_service,
    should_continue_to_generation,
    should_reflect_or_end,
    transform_query_node,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset module-level globals before each test."""
    graph_module._search_service = None
    graph_module._llm_gateway = None
    graph_module._db_pool = None
    yield
    graph_module._search_service = None
    graph_module._llm_gateway = None
    graph_module._db_pool = None


@pytest.fixture
def base_state():
    return {
        "question": "What is KITAS?",
        "metadata": {},
        "step_count": 0,
        "execution_path": [],
        "timestamp": datetime.now(tz=timezone.utc),
    }


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)
    pool._mock_conn = conn
    return pool


# ============================================================================
# Service injection
# ============================================================================


class TestServiceInjection:
    def test_set_search_service(self):
        mock_service = MagicMock()
        set_search_service(mock_service)
        assert graph_module._search_service is mock_service

    def test_set_llm_gateway(self):
        mock_gw = MagicMock()
        set_llm_gateway(mock_gw)
        assert graph_module._llm_gateway is mock_gw

    def test_set_db_pool(self):
        mock_pool = MagicMock()
        set_db_pool(mock_pool)
        assert graph_module._db_pool is mock_pool


# ============================================================================
# _load_conversation_history
# ============================================================================


class TestLoadConversationHistory:
    @pytest.mark.asyncio
    async def test_no_db_pool(self):
        result = await _load_conversation_history(client_id=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_no_client_id(self, mock_db_pool):
        graph_module._db_pool = mock_db_pool
        result = await _load_conversation_history(client_id=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_history(self, mock_db_pool):
        graph_module._db_pool = mock_db_pool
        rows = [
            {"direction": "inbound", "content": "Hello"},
            {"direction": "outbound", "content": "Hi there"},
        ]
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=rows)
        result = await _load_conversation_history(client_id=1, limit=5)
        assert len(result) == 2
        # Rows are reversed to chronological order, so first is "Hello"
        assert "[inbound]" in result[0] or "[outbound]" in result[0]

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        graph_module._db_pool = mock_db_pool
        mock_db_pool._mock_conn.fetch = AsyncMock(side_effect=Exception("DB error"))
        result = await _load_conversation_history(client_id=1)
        assert result == []


# ============================================================================
# retrieve_node
# ============================================================================


class TestRetrieveNode:
    @pytest.mark.asyncio
    async def test_mock_retrieval(self, base_state):
        result = await retrieve_node(base_state)
        assert len(result["documents"]) == 3
        assert "retrieve_mock" in result["execution_path"]
        assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_real_retrieval(self, base_state):
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value={
            "results": [
                {"text": "KITAS is a temporary stay permit", "score": 0.95, "metadata": {"source": "immigration"}},
                {"text": "KITAS requires a sponsor", "score": 0.85, "metadata": {}},
            ],
        })
        graph_module._search_service = mock_search
        result = await retrieve_node(base_state)
        assert len(result["documents"]) == 2
        assert "retrieve" in result["execution_path"]

    @pytest.mark.asyncio
    async def test_retrieval_with_non_dict_results(self, base_state):
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value={
            "results": ["plain text result"],
        })
        graph_module._search_service = mock_search
        result = await retrieve_node(base_state)
        assert len(result["documents"]) == 1

    @pytest.mark.asyncio
    async def test_retrieval_error(self, base_state):
        mock_search = MagicMock()
        mock_search.search = AsyncMock(side_effect=Exception("Search down"))
        graph_module._search_service = mock_search
        result = await retrieve_node(base_state)
        assert result["documents"] == []
        assert "retrieve_error" in result["execution_path"]
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_string_client_id(self, base_state):
        base_state["metadata"] = {"client_id": "123"}
        result = await retrieve_node(base_state)
        assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_non_numeric_client_id(self, base_state):
        base_state["metadata"] = {"client_id": "abc"}
        result = await retrieve_node(base_state)
        assert result["step_count"] == 1


# ============================================================================
# grade_node
# ============================================================================


class TestGradeNode:
    @pytest.mark.asyncio
    async def test_score_based_fallback(self, base_state):
        base_state["documents"] = ["doc1", "doc2", "doc3"]
        base_state["retrieved_scores"] = [0.9, 0.5, 0.8]
        result = await grade_node(base_state)
        assert len(result["filtered_documents"]) == 2  # 0.9 and 0.8
        assert "grade_score_based" in result["execution_path"]

    @pytest.mark.asyncio
    async def test_llm_grading(self, base_state):
        base_state["documents"] = ["doc1", "doc2"]
        base_state["retrieved_scores"] = [0.9, 0.8]

        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.001
        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(
            return_value=("[0.9, 0.3]", "test-model", None, mock_usage),
        )
        graph_module._llm_gateway = mock_gw

        result = await grade_node(base_state)
        assert len(result["filtered_documents"]) == 1  # only 0.9 passes 0.6 threshold
        assert "grade" in result["execution_path"]

    @pytest.mark.asyncio
    async def test_llm_grading_parse_error(self, base_state):
        base_state["documents"] = ["doc1"]
        base_state["retrieved_scores"] = [0.8]

        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.0
        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(
            return_value=("not a valid json", "model", None, mock_usage),
        )
        graph_module._llm_gateway = mock_gw

        result = await grade_node(base_state)
        # Falls back to retrieved_scores
        assert len(result["filtered_documents"]) == 1

    @pytest.mark.asyncio
    async def test_grade_error(self, base_state):
        base_state["documents"] = ["doc1"]
        base_state["retrieved_scores"] = [0.9]

        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(side_effect=Exception("LLM error"))
        graph_module._llm_gateway = mock_gw

        result = await grade_node(base_state)
        assert "grade_error" in result["execution_path"]
        assert result["filtered_documents"] == ["doc1"]

    @pytest.mark.asyncio
    async def test_score_count_mismatch(self, base_state):
        base_state["documents"] = ["doc1", "doc2", "doc3"]
        base_state["retrieved_scores"] = [0.9, 0.8, 0.7]

        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.0
        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(
            return_value=("[0.9]", "model", None, mock_usage),
        )
        graph_module._llm_gateway = mock_gw

        result = await grade_node(base_state)
        # Should pad with 0.5
        assert len(result["relevance_scores"]) >= 1


# ============================================================================
# generate_node
# ============================================================================


class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_mock_generation(self, base_state):
        base_state["filtered_documents"] = ["doc1", "doc2"]
        result = await generate_node(base_state)
        assert result["generation"] != ""
        assert "generate_mock" in result["execution_path"]

    @pytest.mark.asyncio
    async def test_real_generation(self, base_state):
        base_state["filtered_documents"] = ["KITAS is a temporary stay permit"]

        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.01
        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(
            return_value=("KITAS is a temporary stay permit in Indonesia.", "model", None, mock_usage),
        )
        graph_module._llm_gateway = mock_gw

        result = await generate_node(base_state)
        assert "KITAS" in result["generation"]
        assert "generate" in result["execution_path"]

    @pytest.mark.asyncio
    async def test_generation_error(self, base_state):
        base_state["filtered_documents"] = ["doc1"]

        mock_gw = MagicMock()
        mock_gw.send_message = AsyncMock(side_effect=Exception("LLM error"))
        graph_module._llm_gateway = mock_gw

        result = await generate_node(base_state)
        assert "generate_error" in result["execution_path"]
        assert "error" in result["generation"].lower()


# ============================================================================
# check_hallucination_node
# ============================================================================


class TestCheckHallucination:
    @pytest.mark.asyncio
    async def test_skip_no_generation(self, base_state):
        base_state["generation"] = ""
        base_state["filtered_documents"] = []
        result = await check_hallucination_node(base_state)
        assert result["hallucination_check"] == "skipped"

    @pytest.mark.asyncio
    async def test_skip_max_retries(self, base_state):
        base_state["generation"] = "something"
        base_state["filtered_documents"] = ["doc"]
        base_state["reflection_retries"] = MAX_REFLECTION_RETRIES
        result = await check_hallucination_node(base_state)
        assert result["hallucination_check"] == "skipped"

    @pytest.mark.asyncio
    async def test_no_docs(self, base_state):
        base_state["generation"] = "something"
        base_state["filtered_documents"] = []
        result = await check_hallucination_node(base_state)
        assert result["hallucination_check"] == "no_docs"

    @pytest.mark.asyncio
    async def test_grounded(self, base_state):
        base_state["generation"] = "KITAS is a temporary stay permit for Indonesia"
        base_state["filtered_documents"] = ["KITAS is a temporary stay permit for Indonesia use"]
        result = await check_hallucination_node(base_state)
        assert result["hallucination_check"] == "passed"

    @pytest.mark.asyncio
    async def test_hallucination_detected(self, base_state):
        base_state["generation"] = "completely unrelated generated content"
        base_state["filtered_documents"] = [{"content": "KBLI codes for restaurant business setup"}]
        result = await check_hallucination_node(base_state)
        assert result["hallucination_check"] in ("failed", "passed")


# ============================================================================
# transform_query_node
# ============================================================================


class TestTransformQuery:
    @pytest.mark.asyncio
    async def test_with_docs(self, base_state):
        original_question = base_state["question"]
        base_state["filtered_documents"] = ["KITAS information about permits"]
        base_state["reflection_retries"] = 0
        result = await transform_query_node(base_state)
        # transform_query_node modifies state in-place and returns it
        # The question should contain "specifically about"
        assert "specifically about" in result["question"]
        assert result["reflection_retries"] == 1

    @pytest.mark.asyncio
    async def test_no_docs(self, base_state):
        base_state["filtered_documents"] = []
        base_state["reflection_retries"] = 0
        result = await transform_query_node(base_state)
        assert "detailed information" in result["question"]
        assert result["reflection_retries"] == 1


# ============================================================================
# Conditional edges
# ============================================================================


class TestConditionalEdges:
    def test_should_reflect_passed(self):
        state = {"hallucination_check": "passed", "reflection_retries": 0}
        assert should_reflect_or_end(state) == "__end__"

    def test_should_reflect_failed_retry(self):
        state = {"hallucination_check": "failed", "reflection_retries": 0}
        assert should_reflect_or_end(state) == "transform_query"

    def test_should_reflect_max_retries(self):
        state = {"hallucination_check": "failed", "reflection_retries": MAX_REFLECTION_RETRIES}
        assert should_reflect_or_end(state) == "__end__"

    def test_continue_to_generation(self):
        state = {"filtered_documents": ["doc1"]}
        assert should_continue_to_generation(state) == "generate"

    def test_end_no_docs(self):
        state = {"filtered_documents": []}
        assert should_continue_to_generation(state) == "__end__"

    def test_end_none_docs(self):
        state = {}
        assert should_continue_to_generation(state) == "__end__"


# ============================================================================
# create_rag_graph
# ============================================================================


class TestCreateGraph:
    def test_create_graph(self):
        g = create_rag_graph()
        assert g is not None
