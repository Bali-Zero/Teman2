"""
Complex Integration Tests for ReasoningEngine
Tests complex real-world scenarios with multiple tools and edge cases

Coverage:
- Multi-step reasoning with multiple tools
- Complex citation aggregation
- Error recovery scenarios
- Performance optimization scenarios
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

from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.tools.definitions import AgentState, ToolCall


@pytest.mark.integration
@pytest.mark.coverage
class TestReasoningComplexScenarios:
    """Complex integration tests for ReasoningEngine"""

    @pytest.mark.asyncio
    async def test_multi_tool_reasoning_flow(self):
        """Test complex flow with multiple tools in sequence"""
        # Mock multiple tools
        mock_vector_search = MagicMock()
        mock_vector_search.execute = AsyncMock(
            return_value='{"content": "KITAS visa information", "sources": [{"id": "doc1", "score": 0.9}]}'
        )

        mock_calculator = MagicMock()
        mock_calculator.execute = AsyncMock(return_value="42")

        tool_map = {
            "vector_search": mock_vector_search,
            "calculator": mock_calculator,
        }
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS and calculate 6*7?", max_steps=10)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_idx = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return ("Action: vector_search('KITAS')", "gemini-2.0-flash", None)
            elif call_idx == 2:
                return ("Action: calculator('6*7')", "gemini-2.0-flash", None)
            else:
                return ("Final Answer: KITAS is a permit and 6*7=42", "gemini-2.0-flash", None)

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        tool_calls = [
            ToolCall(tool_name="vector_search", arguments={"query": "KITAS"}),
            ToolCall(tool_name="calculator", arguments={"expression": "6*7"}),
            None,
        ]
        call_idx_parse = 0

        def mock_parse_tool_call(*args, **kwargs):
            nonlocal call_idx_parse
            if call_idx_parse < len(tool_calls):
                result = tool_calls[call_idx_parse]
                call_idx_parse += 1
                return result
            return None

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_tool_call
            ):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS and calculate 6*7?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Verify both tools were executed
        assert mock_vector_search.execute.called
        assert mock_calculator.execute.called
        assert result_state.final_answer is not None
        assert len(result_state.steps) >= 2

    @pytest.mark.asyncio
    async def test_complex_citation_aggregation(self):
        """Test aggregation of citations from multiple vector_search calls"""
        mock_tool = MagicMock()
        call_count = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"content": "KITAS info part 1", "sources": [{"id": "doc1", "score": 0.9}]}'
            else:
                return '{"content": "KITAS info part 2", "sources": [{"id": "doc2", "score": 0.85}, {"id": "doc3", "score": 0.8}]}'

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
                return ("Action: vector_search('KITAS')", "gemini-2.0-flash", None)
            else:
                return ("Final Answer: KITAS is a permit", "gemini-2.0-flash", None)

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, _, _ = await engine.execute_react_loop(
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
        assert len(result_state.sources) >= 1

    @pytest.mark.asyncio
    async def test_error_recovery_after_tool_failure(self):
        """Test that system recovers after a tool execution failure"""
        # First tool fails, second succeeds
        mock_tool1 = MagicMock()
        mock_tool1.execute = AsyncMock(side_effect=Exception("Tool 1 failed"))

        mock_tool2 = MagicMock()
        mock_tool2.execute = AsyncMock(return_value="Tool 2 succeeded")

        tool_map = {
            "tool1": mock_tool1,
            "tool2": mock_tool2,
        }
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Test query", max_steps=5)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_idx = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return ("Action: tool1()", "gemini-2.0-flash", None)
            elif call_idx == 2:
                return ("Action: tool2()", "gemini-2.0-flash", None)
            elif call_idx == 3:
                return ("Final Answer: Success", "gemini-2.0-flash", None)
            else:
                return ("Final Answer: Success", "gemini-2.0-flash", None)

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        tool_calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={}),
            None,
        ]
        call_idx_parse = 0

        def mock_parse_tool_call(*args, **kwargs):
            nonlocal call_idx_parse
            if call_idx_parse < len(tool_calls):
                result = tool_calls[call_idx_parse]
                call_idx_parse += 1
                return result
            return None

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_tool_call
            ):
                result_state, _, _ = await engine.execute_react_loop(
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

        # Should recover and continue
        assert result_state is not None
        assert mock_tool2.execute.called

    @pytest.mark.asyncio
    async def test_max_steps_reached_scenario(self):
        """Test scenario where max_steps is reached without final answer"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="Complex query", max_steps=2)
        state.context_gathered = ["Some context " * 20]
        state.sources = [{"id": 1, "score": 0.9}]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Still thinking...", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="Complex query",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should generate answer from context when max_steps reached
        assert result_state.current_step == state.max_steps
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_streaming_mode_complex_flow(self):
        """Test complex streaming flow with tools and final answer"""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": [{"id": "doc1", "score": 0.9}]}'
        )

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
            if call_idx == 1:
                return ("Action: vector_search('KITAS')", "gemini-2.0-flash", None)
            else:
                return ("Final Answer: KITAS is a permit", "gemini-2.0-flash", None)

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
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

        # Verify various event types were yielded
        event_types = [e.get("type") for e in events]
        assert "thinking" in event_types or "tool_call" in event_types or "token" in event_types
        assert len(events) > 0
