"""
Additional Coverage Tests for ReasoningEngine
Tests missing areas to improve coverage from 40.43% to 75%+

Coverage targets:
- Tool execution paths (lines 210-213, 220-229, 238-296)
- ReAct loop logic (lines 238-296)
- Policy enforcement edge cases (lines 356-393)
- Final answer generation (lines 416-480)
- Streaming mode (lines 514-515, 528-531, 538-545, 553-598, 604, 614-615, 626, 646-682, 685-686, 697, 701-714, 727, 746-876)
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
class TestReasoningToolExecution:
    """Test tool execution paths in ReasoningEngine"""

    @pytest.mark.asyncio
    async def test_tool_execution_with_valid_tool_call(self):
        """Test tool execution when valid tool call is parsed"""
        # Create a proper mock tool that implements BaseTool interface
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Found relevant documents about KITAS")

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
                    "Thought: I need to search for KITAS information. Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )
            else:
                return (
                    "Answer: KITAS is a temporary residence permit",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        # Mock parse_tool_call to return a valid tool call, then None
        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        parse_call_count = 0

        def mock_parse_fn(*args, **kwargs):
            nonlocal parse_call_count
            parse_call_count += 1
            if parse_call_count == 1:
                return mock_tool_call
            else:
                return None

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_fn):
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

        # Verify tool was executed
        assert "vector_search" in tool_map
        mock_tool.execute.assert_called()

        # Verify context was gathered
        assert len(result_state.context_gathered) > 0

    @pytest.mark.asyncio
    async def test_tool_execution_with_multiple_tools(self):
        """Test tool execution with multiple tool calls"""
        # Create proper mock tools
        mock_vector_search = MagicMock()
        mock_vector_search.execute = AsyncMock(return_value="Document 1 about KITAS")
        mock_calculator = MagicMock()
        mock_calculator.execute = AsyncMock(return_value="42")

        tool_map = {
            "vector_search": mock_vector_search,
            "calculator": mock_calculator,
        }
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS and calculate 6*7?", max_steps=5)
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
            elif call_count == 2:
                return ("Action: calculator('6*7')", "gemini-2.0-flash", None, mock_token_usage())
            else:
                return (
                    "Answer: KITAS is a permit and 6*7=42",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        # Mock parse_tool_call to return different tools
        tool_calls = [
            ToolCall(tool_name="vector_search", arguments={"query": "KITAS"}),
            ToolCall(tool_name="calculator", arguments={"expression": "6*7"}),
            None,  # Final answer
        ]
        call_idx = 0

        def mock_parse_tool_call(*args, **kwargs):
            nonlocal call_idx
            if call_idx < len(tool_calls):
                result = tool_calls[call_idx]
                call_idx += 1
                return result
            return None

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_tool_call
            ):
                result_state, _, __, ___ = await engine.execute_react_loop(
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

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self):
        """Test error handling when tool execution fails"""
        # Create mock tool that raises exception
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(side_effect=Exception("Tool execution failed"))

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
                return (
                    "Answer: I encountered an error",
                    "gemini-2.0-flash",
                    None,
                    mock_token_usage(),
                )

        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        parse_call_count = 0

        def mock_parse_fn(*args, **kwargs):
            nonlocal parse_call_count
            parse_call_count += 1
            if parse_call_count == 1:
                return mock_tool_call
            else:
                return None

        tool_execution_counter = {"count": 0}
        # Mock tracing properly using contextlib.nullcontext
        from contextlib import nullcontext

        with patch(
            "services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch("services.rag.agentic.reasoning.parse_tool_call", side_effect=mock_parse_fn):
                # Tool execution errors should be raised (not silently caught)
                with pytest.raises(Exception, match="Tool execution failed"):
                    await engine.execute_react_loop(
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

        # Exception was raised as expected
        assert True

    @pytest.mark.asyncio
    async def test_tool_execution_with_native_function_calling(self):
        """Test tool execution with native function calling (Gemini)"""
        # Create proper mock tool
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Found documents")

        tool_map = {"vector_search": mock_tool}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        chat = MagicMock()

        # Mock response object with native function call
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_candidate.content.parts = [mock_part]

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
                llm_gateway.send_message = AsyncMock(
                    return_value=("Answer", "gemini-2.0-flash", mock_response, mock_token_usage())
                )

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

        # Verify tool was called
        assert mock_tool.execute.called


@pytest.mark.unit
@pytest.mark.coverage
class TestReasoningStreamingMode:
    """Test streaming mode coverage"""

    @pytest.mark.asyncio
    async def test_streaming_mode_basic_flow(self):
        """Test basic streaming mode execution"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = ["KITAS is a temporary residence permit " * 10]
        state.sources = [{"id": 1, "score": 0.9}]

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

        events = []
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            async for event in engine.execute_react_loop_stream(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is KITAS?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            ):
                events.append(event)

        # Verify events were yielded
        assert len(events) > 0
        # Should have evidence_score event
        evidence_events = [e for e in events if e.get("type") == "evidence_score"]
        assert len(evidence_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_with_tool_calls(self):
        """Test streaming mode with tool execution"""
        # Create proper mock tool
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Found documents about KITAS")

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

        # Verify tool call events were yielded
        tool_events = [e for e in events if e.get("type") == "tool_call"]
        assert len(tool_events) > 0 or tool_map["vector_search"].called

    @pytest.mark.asyncio
    async def test_streaming_mode_error_handling(self):
        """Test streaming mode error handling"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=2)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        from google.api_core.exceptions import ResourceExhausted

        llm_gateway.send_message = AsyncMock(side_effect=ResourceExhausted("Rate limit exceeded"))
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should yield error event
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_abstain_policy(self):
        """Test streaming mode ABSTAIN policy with weak evidence"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is XYZ?", max_steps=1)
        state.context_gathered = []  # No context = weak evidence
        state.sources = []

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            async for event in engine.execute_react_loop_stream(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is XYZ?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter=tool_execution_counter,
            ):
                events.append(event)

        # Should have evidence_score event
        evidence_events = [e for e in events if e.get("type") == "evidence_score"]
        assert len(evidence_events) > 0

        # Final answer should be abstain message
        final_events = [e for e in events if e.get("type") == "final_answer"]
        if final_events:
            final_answer = final_events[0].get("data", "")
            assert (
                "non ho trovato informazioni" in final_answer.lower()
                or "dispiace" in final_answer.lower()
            )

    @pytest.mark.asyncio
    async def test_streaming_mode_warning_policy(self):
        """Test streaming mode warning injection for weak evidence"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        # Weak evidence: some context but not strong
        state.context_gathered = ["Some information about KITAS"]
        state.sources = [{"id": 1, "score": 0.5}]  # Low score

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer: KITAS is a permit", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            async for event in engine.execute_react_loop_stream(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is KITAS?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            ):
                events.append(event)

        # Should have evidence_score event
        evidence_events = [e for e in events if e.get("type") == "evidence_score"]
        assert len(evidence_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_mode_max_steps_reached(self):
        """Test streaming mode when max_steps is reached"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS information " * 20]
        state.sources = [{"id": 1, "score": 0.9}]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Thought: Still thinking...",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should complete even when max_steps reached
        assert len(events) > 0


@pytest.mark.unit
@pytest.mark.coverage
class TestReasoningPolicyEnforcement:
    """Test policy enforcement edge cases"""

    @pytest.mark.asyncio
    async def test_policy_override_existing_answer_with_weak_evidence(self):
        """Test that weak evidence overrides existing final_answer"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is XYZ?", max_steps=1)
        state.context_gathered = []  # No context = weak evidence
        state.sources = []
        state.final_answer = "Some answer"  # Pre-existing answer

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, __, ___ = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is XYZ?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Weak evidence should override existing answer
        assert (
            "non ho trovato informazioni" in result_state.final_answer.lower()
            or "dispiace" in result_state.final_answer.lower()
        )

    @pytest.mark.asyncio
    async def test_policy_final_answer_generation_with_strong_evidence(self):
        """Test final answer generation when evidence is strong"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS visa requirements " * 30]  # Strong context
        state.sources = [
            {"id": 1, "score": 0.9},
            {"id": 2, "score": 0.85},
            {"id": 3, "score": 0.8},
            {"id": 4, "score": 0.75},
        ]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "KITAS is a temporary residence permit for Indonesia",
                "gemini-2.0-flash",
                None,
                mock_token_usage(),
            )
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, __, ___ = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is KITAS?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Should generate answer (not abstain)
        assert result_state.final_answer
        assert "non ho trovato informazioni" not in result_state.final_answer.lower()
        assert result_state.evidence_score >= 0.6
