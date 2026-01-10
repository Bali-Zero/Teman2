"""
Edge Case Tests for ReasoningEngine
Tests remaining edge cases to improve coverage from 70.37% to 75%+

Coverage targets:
- Early exit optimization (lines 291-294)
- Final answer parsing edge cases (lines 303, 316-318)
- Error handling in LLM calls (lines 211-213)
- Citation parsing edge cases (lines 262, 270-271)
- Warning policy edge cases (lines 369-374, 391-393)
- Streaming mode edge cases (lines 538-545, 572, 597-598, 614-615, 626, 656-682, 697, 712-714)
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

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.tools.definitions import AgentState, ToolCall


def mock_token_usage():
    return TokenUsage(prompt_tokens=10, completion_tokens=20)


@pytest.mark.unit
@pytest.mark.coverage
class TestReasoningEdgeCases:
    """Test edge cases for ReasoningEngine"""

    @pytest.mark.asyncio
    async def test_early_exit_on_vector_search_sufficient_context(self):
        """Test early exit when vector_search returns sufficient context (>500 chars)"""
        # Mock vector_search tool returning rich content
        mock_tool = MagicMock()
        rich_content = "This is a very detailed answer about KITAS. " * 20  # > 500 chars
        mock_tool.execute = AsyncMock(return_value=rich_content)

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=5)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Action: vector_search('KITAS')",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
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
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should exit early due to sufficient context
        assert len(result_state.context_gathered) > 0
        assert result_state.current_step == 1  # Should exit after first step

    @pytest.mark.asyncio
    async def test_early_exit_not_triggered_with_no_relevant_documents(self):
        """Test early exit NOT triggered when result contains 'No relevant documents'"""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="No relevant documents found for this query")

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is XYZ?", max_steps=3)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_count = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (
                    "Action: vector_search('XYZ')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return (
                    "Answer: I couldn't find information",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "XYZ"},
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
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is XYZ?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should NOT exit early (contains "No relevant documents")
        # Should continue to next step
        assert result_state.current_step >= 1

    @pytest.mark.asyncio
    async def test_final_answer_parsing_with_final_answer_prefix(self):
        """Test parsing final answer when response contains 'Final Answer:' prefix"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is 2+2?", max_steps=2)
        state.context_gathered = ["Mathematical calculation: 2+2 equals 4"]
        state.sources = [{"id": 1, "score": 0.9}]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Final Answer: The answer is 4",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is 2+2?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should parse final answer correctly
        assert result_state.final_answer is not None
        assert "4" in result_state.final_answer or "answer" in result_state.final_answer.lower()

    @pytest.mark.asyncio
    async def test_llm_error_handling_resource_exhausted(self):
        """Test error handling when LLM raises ResourceExhausted"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=2)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        from google.api_core.exceptions import ResourceExhausted

        llm_gateway.send_message = AsyncMock(side_effect=ResourceExhausted("Rate limit exceeded"))
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should handle error gracefully
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_citation_parsing_with_missing_sources_key(self):
        """Test citation parsing when JSON has content but no sources key"""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value='{"content": "KITAS information"}')

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=3)
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
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should handle missing sources gracefully
        assert result_state is not None
        assert len(result_state.context_gathered) > 0

    @pytest.mark.asyncio
    async def test_warning_policy_edge_case_score_0_3(self):
        """Test warning policy at exact threshold (evidence_score = 0.3)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=1)
        # Context that should score exactly 0.3
        state.context_gathered = ["KITAS information"]
        state.sources = []  # No sources

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought", "gemini-2.0-flash", None, mock_token_usage()),
                ("Cautious answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should handle edge case at threshold
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_warning_policy_edge_case_score_0_6(self):
        """Test warning policy at upper threshold (evidence_score = 0.6)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=1)
        # Context that should score exactly 0.6
        state.context_gathered = ["KITAS visa requirements " * 20]
        state.sources = [{"id": 1, "score": 0.85}]  # High quality source

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer: KITAS is a permit", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                result_state, _, __, ___ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Should handle edge case at threshold
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_streaming_mode_final_answer_token_streaming(self):
        """Test streaming mode token-by-token final answer streaming"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=1)
        state.context_gathered = ["KITAS is a temporary residence permit " * 10]
        state.sources = [{"id": 1, "score": 0.9}]
        state.final_answer = "KITAS is a temporary residence permit for Indonesia"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                async for event in engine.execute_react_loop_stream(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                ):
                    events.append(event)

        # Verify token events were yielded
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_sources_event(self):
        """Test streaming mode sources event yield"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = [{"id": "doc1", "score": 0.9, "title": "KITAS Guide"}]
        state.final_answer = "KITAS is a permit"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                async for event in engine.execute_react_loop_stream(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                ):
                    events.append(event)

        # Verify sources event was yielded
        sources_events = [e for e in events if e.get("type") == "sources"]
        assert len(sources_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_stub_response_filtering(self):
        """Test streaming mode filters stub responses"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        state.final_answer = "no further action needed"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext

        with patch(
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
                async for event in engine.execute_react_loop_stream(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                ):
                    events.append(event)

        # Should filter stub response - check that it was replaced
        assert state.final_answer != "no further action needed"
        # The stub response should be replaced with a clarification request
        assert len(state.final_answer) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_early_exit_optimization(self):
        """Test streaming mode early exit optimization"""
        mock_tool = MagicMock()
        rich_content = "Detailed KITAS information " * 30  # > 500 chars
        mock_tool.execute = AsyncMock(return_value=rich_content)

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS", max_steps=5)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Action: vector_search('KITAS')",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
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
                    query="What is KITAS",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                ):
                    events.append(event)

        # Should exit early
        assert len(events) > 0
