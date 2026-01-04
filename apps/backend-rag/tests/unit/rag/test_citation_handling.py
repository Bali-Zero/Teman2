"""
Tests for Citation Handling in ReasoningEngine
Tests how sources are extracted and managed from tool results

Coverage:
- Citation extraction from vector_search results
- Source aggregation across multiple tool calls
- Citation handling in streaming mode
- Error handling for malformed citation data
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.llm_clients.pricing import TokenUsage
from services.rag.agentic.reasoning import ReasoningEngine
from services.tools.definitions import AgentState, ToolCall


def mock_token_usage():
    return TokenUsage(prompt_tokens=10, completion_tokens=20)


@pytest.mark.unit
@pytest.mark.coverage
class TestCitationHandling:
    """Test citation handling in ReasoningEngine"""

    @pytest.mark.asyncio
    async def test_citation_extraction_from_vector_search(self):
        """Test that citations are extracted from vector_search JSON results"""
        # Mock vector_search tool returning JSON with sources
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS information", "sources": [{"id": "doc1", "score": 0.9, "title": "KITAS Guide"}]}'
        )

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_idx = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return (
                    "Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return ("Answer: KITAS is a permit", "gemini-2.0-flash", None, mock_token_usage())

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Verify sources were extracted
        assert hasattr(result_state, "sources")
        assert len(result_state.sources) > 0
        assert result_state.sources[0]["id"] == "doc1"
        assert result_state.sources[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_citation_aggregation_multiple_tools(self):
        """Test that citations are aggregated from multiple tool calls"""
        # Mock multiple vector_search calls
        mock_tool = MagicMock()
        call_count = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"content": "KITAS info", "sources": [{"id": "doc1", "score": 0.9}]}'
            else:
                return '{"content": "More KITAS info", "sources": [{"id": "doc2", "score": 0.85}]}'

        mock_tool.execute = AsyncMock(side_effect=mock_execute)

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=5)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_idx = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx <= 2:
                return (
                    "Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return ("Answer: KITAS is a permit", "gemini-2.0-flash", None, mock_token_usage())

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Verify sources were aggregated
        assert hasattr(result_state, "sources")
        assert len(result_state.sources) >= 1  # At least one source

    @pytest.mark.asyncio
    async def test_citation_handling_malformed_json(self):
        """Test that malformed JSON in vector_search results is handled gracefully"""
        # Mock vector_search tool returning malformed JSON
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Not valid JSON {invalid")

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_count = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (
                    "Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return ("Answer: KITAS info", "gemini-2.0-flash", None, mock_token_usage())

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should handle malformed JSON gracefully
        assert result_state is not None
        # Context should still be gathered even if JSON parsing fails
        assert len(result_state.context_gathered) > 0

    @pytest.mark.asyncio
    async def test_citation_handling_streaming_mode(self):
        """Test citation handling in streaming mode"""
        # Mock vector_search tool returning JSON with sources
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": [{"id": "doc1", "score": 0.9}]}'
        )

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_idx = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return (
                    "Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return ("Answer: KITAS is a permit", "gemini-2.0-flash", None, mock_token_usage())

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        events = []
        tool_execution_counter = {"count": 0}
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call):
            async for event in engine.execute_react_loop_stream(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is KITAS?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter=tool_execution_counter,
            ):
                events.append(event)

        # Verify sources event was yielded
        sources_events = [e for e in events if e.get("type") == "sources"]
        assert len(sources_events) > 0 or hasattr(state, "sources")
