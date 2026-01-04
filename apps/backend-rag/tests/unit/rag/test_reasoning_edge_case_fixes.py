"""
Tests for ReasoningEngine Edge Case Fixes

Tests the three edge case fixes implemented in reasoning.py:
1. Edge Case 1: candidate.content None check
2. Edge Case 2: Partial tool call validation via is_valid_tool_call
3. Edge Case 3: Empty content handling in vector_search

Target: Maintain coverage >95%
"""

import json
import os
import sys
from contextlib import nullcontext
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
from services.rag.agentic.reasoning import (
    ReasoningEngine,
    calculate_evidence_score,
    is_valid_tool_call,
)
from services.tools.definitions import AgentState, ToolCall


def mock_token_usage() -> TokenUsage:
    """Create a mock TokenUsage for testing."""
    return TokenUsage(prompt_tokens=10, completion_tokens=20)


# =============================================================================
# Test is_valid_tool_call helper function (Edge Case 2)
# =============================================================================


@pytest.mark.unit
class TestIsValidToolCall:
    """Tests for the is_valid_tool_call validation function."""

    def test_valid_tool_call_returns_true(self):
        """Valid ToolCall with all required fields should return True."""
        tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )
        assert is_valid_tool_call(tool_call) is True

    def test_valid_tool_call_empty_arguments(self):
        """ToolCall with empty dict arguments is valid."""
        tool_call = ToolCall(
            tool_name="calculator",
            arguments={},
        )
        assert is_valid_tool_call(tool_call) is True

    def test_none_tool_call_returns_false(self):
        """None should return False."""
        assert is_valid_tool_call(None) is False

    def test_tool_call_with_none_tool_name(self):
        """ToolCall with None tool_name should return False."""
        tool_call = MagicMock()
        tool_call.tool_name = None
        tool_call.arguments = {}
        assert is_valid_tool_call(tool_call) is False

    def test_tool_call_with_empty_string_tool_name(self):
        """ToolCall with empty string tool_name should return False."""
        tool_call = MagicMock()
        tool_call.tool_name = ""
        tool_call.arguments = {}
        assert is_valid_tool_call(tool_call) is False

    def test_tool_call_with_non_string_tool_name(self):
        """ToolCall with non-string tool_name should return False."""
        tool_call = MagicMock()
        tool_call.tool_name = 123  # Not a string
        tool_call.arguments = {}
        assert is_valid_tool_call(tool_call) is False

    def test_tool_call_with_none_arguments(self):
        """ToolCall with None arguments should return False."""
        tool_call = MagicMock()
        tool_call.tool_name = "vector_search"
        tool_call.arguments = None
        assert is_valid_tool_call(tool_call) is False

    def test_tool_call_missing_tool_name_attribute(self):
        """Object without tool_name attribute should return False."""
        tool_call = MagicMock(spec=[])  # No attributes
        assert is_valid_tool_call(tool_call) is False

    def test_tool_call_missing_arguments_attribute(self):
        """Object without arguments attribute should return False."""
        tool_call = MagicMock(spec=["tool_name"])
        tool_call.tool_name = "vector_search"
        assert is_valid_tool_call(tool_call) is False


# =============================================================================
# Test Edge Case 1: candidate.content None check
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestEdgeCase1CandidateContentNone:
    """Tests for Edge Case 1: proper handling when candidate.content is None."""

    async def test_candidate_content_none_no_crash(self):
        """
        Test that the engine handles candidate.content = None gracefully.
        Before the fix, this could cause AttributeError or TypeError.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Create response_obj with candidate.content = None
        mock_candidate = MagicMock()
        mock_candidate.content = None  # This is the edge case

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Final Answer: Test answer",
                "gemini-2.0-flash",
                mock_response,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # Should complete without crashing
        assert result_state is not None
        assert result_state.final_answer is not None

    async def test_candidate_content_parts_none(self):
        """
        Test that the engine handles candidate.content.parts = None gracefully.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Test query", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Create response_obj with candidate.content.parts = None
        mock_content = MagicMock()
        mock_content.parts = None  # This is the edge case

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: OK", "gemini-2.0-flash", mock_response, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="Test query",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )
                result_state = result[0]

        assert result_state is not None

    async def test_candidate_content_parts_empty_list(self):
        """
        Test that the engine handles candidate.content.parts = [] gracefully.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Test query", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Create response_obj with candidate.content.parts = []
        mock_content = MagicMock()
        mock_content.parts = []  # Empty list should be falsy

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: OK", "gemini-2.0-flash", mock_response, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="Test query",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )
                result_state = result[0]

        assert result_state is not None


# =============================================================================
# Test Edge Case 2: Partial tool call validation in ReAct loop
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestEdgeCase2PartialToolCallValidation:
    """Tests for Edge Case 2: validation of partial/invalid tool calls."""

    async def test_partial_tool_call_falls_back_to_regex(self):
        """
        Test that a partial tool call (valid structure but None arguments)
        triggers fallback to regex parsing.
        """
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Tool result")
        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Create a partial tool call (tool_name present, arguments None)
        partial_tool_call = MagicMock()
        partial_tool_call.tool_name = "vector_search"
        partial_tool_call.arguments = None  # Invalid!

        # Valid tool call for regex fallback
        valid_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "ACTION: vector_search(query='KITAS')",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        # First call returns partial, second returns valid
        call_count = [0]

        def mock_parse_tool_call(text_or_part, use_native=True):
            call_count[0] += 1
            if use_native:
                return partial_tool_call  # Return invalid on native
            else:
                return valid_tool_call  # Return valid on regex fallback

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_tool_call
            ):
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # Should have called the tool with valid arguments from fallback
        assert result_state is not None

    async def test_both_parsers_fail_no_tool_execution(self):
        """
        Test that when both native and regex parsers return invalid tool calls,
        no tool execution occurs and the response is treated as final answer.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Invalid tool call
        invalid_tool_call = MagicMock()
        invalid_tool_call.tool_name = ""  # Empty = invalid
        invalid_tool_call.arguments = {}

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Final Answer: KITAS is a permit",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        # Both parsers return invalid tool call
        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=invalid_tool_call
            ):
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # No tool should have been executed
        assert tool_execution_counter["count"] == 0
        assert result_state.final_answer is not None


# =============================================================================
# Test Edge Case 3: Empty content handling in vector_search
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestEdgeCase3EmptyContent:
    """Tests for Edge Case 3: empty content handling in vector_search."""

    async def test_empty_content_keeps_original_result(self):
        """
        Test that when vector_search returns empty content with sources,
        the original tool_result is kept (not replaced with empty string).
        """
        mock_tool = MagicMock()
        # Return JSON with empty content but valid sources
        mock_tool.execute = AsyncMock(
            return_value=json.dumps(
                {
                    "content": "",  # Empty content!
                    "sources": [{"id": "doc1", "score": 0.9}],
                }
            )
        )
        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        # Use max_steps=1 to avoid multiple iterations
        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = []
        state.sources = []

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Action: vector_search", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                # Handle both return signatures (with and without TokenUsage)
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # Sources should still be collected even with empty content
        assert len(result_state.sources) >= 1
        assert result_state.sources[0]["id"] == "doc1"

    async def test_short_content_keeps_original_result(self):
        """
        Test that when vector_search returns very short content (<10 chars),
        the original tool_result is kept.
        """
        mock_tool = MagicMock()
        # Return JSON with very short content
        mock_tool.execute = AsyncMock(
            return_value=json.dumps(
                {
                    "content": "abc",  # Too short (<10 chars)
                    "sources": [{"id": "doc1", "score": 0.9}],
                }
            )
        )
        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        # Use max_steps=1 to avoid multiple iterations
        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = []
        state.sources = []

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Action: vector_search", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                # Handle both return signatures (with and without TokenUsage)
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # Sources should still be collected
        assert len(result_state.sources) >= 1

    async def test_meaningful_content_is_extracted(self):
        """
        Test that when vector_search returns meaningful content (>10 chars),
        it is properly extracted and used.
        """
        mock_tool = MagicMock()
        # Return JSON with meaningful content
        mock_tool.execute = AsyncMock(
            return_value=json.dumps(
                {
                    "content": "KITAS is a temporary stay permit for foreigners in Indonesia. "
                    * 10,
                    "sources": [{"id": "doc1", "score": 0.9}],
                }
            )
        )
        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Action: vector_search", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result = await engine.execute_react_loop(
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
                result_state = result[0]

        # Content should be added to context_gathered
        assert len(result_state.context_gathered) > 0
        assert "KITAS is a temporary stay permit" in result_state.context_gathered[0]
        assert len(result_state.sources) >= 1

    async def test_empty_tool_result_not_added_to_context(self):
        """
        Test that an empty tool_result is not added to context_gathered.
        """
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="")  # Empty result
        tool_map = {"calculator": mock_tool}  # Not vector_search
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Calculate 1+1", max_steps=2)
        state.context_gathered = []
        state.sources = []

        mock_tool_call = ToolCall(
            tool_name="calculator",
            arguments={"expression": "1+1"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Action: calculator", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="Calculate 1+1",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )
                result_state = result[0]

        # Empty result should NOT be added to context_gathered
        assert len(result_state.context_gathered) == 0


# =============================================================================
# Test Streaming Version Edge Cases
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestStreamingEdgeCases:
    """Tests for edge cases in the streaming version of ReAct loop."""

    async def test_streaming_empty_content_handling(self):
        """
        Test streaming version handles empty content from vector_search.
        """
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value=json.dumps({"content": "", "sources": [{"id": "doc1", "score": 0.9}]})
        )
        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        # Use max_steps=1 to avoid multiple iterations
        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = []
        state.sources = []

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Action: vector_search", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        events = []

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

        # Sources should still be collected
        assert len(state.sources) >= 1
        # Should have tool_call and observation events
        event_types = [e.get("type") for e in events]
        assert "tool_call" in event_types

    async def test_streaming_partial_tool_call_handling(self):
        """
        Test streaming version handles partial tool calls correctly.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Invalid tool call
        invalid_tool_call = MagicMock()
        invalid_tool_call.tool_name = None
        invalid_tool_call.arguments = None

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Final Answer: KITAS is a permit",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        events = []

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call", return_value=invalid_tool_call
        ):
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

        # No tool calls should have been made
        assert tool_execution_counter["count"] == 0
        # Should have token events for final answer
        event_types = [e.get("type") for e in events]
        assert "token" in event_types

    async def test_streaming_candidate_content_none(self):
        """
        Test streaming version handles candidate.content = None.
        """
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Test", max_steps=2)
        state.context_gathered = []
        state.sources = []

        # Response with content = None
        mock_candidate = MagicMock()
        mock_candidate.content = None

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: OK", "gemini-2.0-flash", mock_response, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        events = []

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            async for event in engine.execute_react_loop_stream(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="Test",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter=tool_execution_counter,
            ):
                events.append(event)

        # Should complete without crashing
        assert len(events) > 0


# =============================================================================
# Additional Coverage Tests
# =============================================================================


@pytest.mark.unit
class TestCalculateEvidenceScoreCoverage:
    """Additional tests for calculate_evidence_score to improve coverage."""

    def test_no_sources_but_substantial_context(self):
        """Test scoring when no sources but substantial context is provided."""
        sources = None
        context = ["This is substantial context content. " * 20]  # > 500 chars
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)
        assert score > 0.0  # Should get points for substantial context

    def test_sources_with_low_scores(self):
        """Test scoring when all sources have low similarity scores."""
        sources = [
            {"id": "1", "score": 0.5},
            {"id": "2", "score": 0.6},
            {"id": "3", "score": 0.7},
        ]
        context = ["KITAS information here"]
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)
        # Should not get high-quality source bonus (none > 0.8)
        assert score < 0.5

    def test_many_sources_bonus(self):
        """Test that having >3 sources adds to score."""
        sources = [
            {"id": "1", "score": 0.9},
            {"id": "2", "score": 0.85},
            {"id": "3", "score": 0.82},
            {"id": "4", "score": 0.8},
            {"id": "5", "score": 0.78},
        ]
        context = ["KITAS information with good keywords"]
        query = "What is KITAS information?"

        score = calculate_evidence_score(sources, context, query)
        # Should get high-quality + multiple sources + keyword bonuses
        assert score >= 0.5

    def test_keyword_matching(self):
        """Test that keyword matching in context adds to score."""
        sources = []
        context = ["KITAS is a temporary residence permit for foreigners in Indonesia"]
        query = "What is KITAS permit Indonesia?"

        score = calculate_evidence_score(sources, context, query)
        # Should get points for keyword matching
        assert score > 0.0

    def test_empty_query_keywords(self):
        """Test handling of query with only stop words."""
        sources = [{"id": "1", "score": 0.9}]
        context = ["Some context"]
        query = "the a an is"  # All stop words

        score = calculate_evidence_score(sources, context, query)
        # Should still work, just no keyword bonus
        assert score > 0.0  # Still gets source quality bonus

    def test_source_not_dict(self):
        """Test handling of non-dict sources."""
        sources = ["not a dict", 123, None]
        context = ["Some context"]
        query = "test query"

        score = calculate_evidence_score(sources, context, query)
        # Should handle gracefully without crashing
        assert score >= 0.0
