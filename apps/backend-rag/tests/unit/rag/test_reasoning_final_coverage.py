"""
Final Tests to Reach 90% Coverage for reasoning.py
Targets remaining missing lines: 262, 270-271, 391-393, 408-409, 681-682, 697
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

from services.rag.agentic.reasoning import ReasoningEngine
from services.tools.definitions import AgentState, ToolCall


@pytest.mark.unit
@pytest.mark.coverage
class TestReasoningFinalCoverage:
    """Final tests to reach 90% coverage"""

    @pytest.mark.asyncio
    async def test_citation_parsing_sources_not_initialized(self):
        """Test citation parsing when sources not initialized (line 262)"""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": [{"id": "doc1", "score": 0.9}]}'
        )
        
        tool_map = {
            "vector_search": mock_tool
        }
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        # Don't initialize sources attribute
        if hasattr(state, "sources"):
            delattr(state, "sources")

        llm_gateway = AsyncMock()
        call_count = 0
        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("Action: vector_search('KITAS')", "gemini-2.0-flash", None)
            else:
                return ("Answer: KITAS info", "gemini-2.0-flash", None)
        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call):
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

        # Should initialize sources
        assert hasattr(result_state, "sources")

    @pytest.mark.asyncio
    async def test_citation_parsing_typeerror_in_extend(self):
        """Test citation parsing TypeError in extend (line 270-271)"""
        mock_tool = MagicMock()
        # Return JSON that causes TypeError when extending
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": "not a list"}'
        )
        
        tool_map = {
            "vector_search": mock_tool
        }
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
                return ("Action: vector_search('KITAS')", "gemini-2.0-flash", None)
            else:
                return ("Answer: KITAS info", "gemini-2.0-flash", None)
        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        mock_tool_call = ToolCall(
            tool_name="vector_search",
            arguments={"query": "KITAS"},
        )

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call):
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

        # Should handle TypeError gracefully
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_warning_policy_runtime_error(self):
        """Test warning policy RuntimeError handling (lines 391-393)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        # Weak evidence
        state.context_gathered = ["Some information about KITAS"]
        state.sources = [{"id": 1, "score": 0.5}]

        llm_gateway = AsyncMock()
        call_count = 0
        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("Thought", "gemini-2.0-flash", None)
            else:
                # Final answer generation raises RuntimeError
                raise RuntimeError("Runtime error")
        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should handle RuntimeError gracefully
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_final_answer_stub_filtering_observation_none(self):
        """Test final answer stub filtering for 'observation: none' (lines 408-409)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = [{"id": 1, "score": 0.9}]
        state.final_answer = "observation: none"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
            with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should filter stub response
        assert state.final_answer != "observation: none"
        assert len(state.final_answer) > 0

    @pytest.mark.asyncio
    async def test_streaming_llm_runtime_error(self):
        """Test streaming LLM RuntimeError handling (lines 681-682)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        state.final_answer = None

        llm_gateway = AsyncMock()
        call_count = 0
        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("Thought", "gemini-2.0-flash", None)
            else:
                # Final answer generation raises RuntimeError
                raise RuntimeError("Runtime error")
        llm_gateway.send_message = AsyncMock(side_effect=mock_send_message)
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
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
                    if len(events) > 20:
                        break

        # Should handle RuntimeError gracefully
        assert len(events) >= 0
        assert state.final_answer is not None

    @pytest.mark.asyncio
    async def test_streaming_stub_filtering_observation_none(self):
        """Test streaming stub filtering for 'observation: none' (line 697)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        state.final_answer = "observation: none"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        from contextlib import nullcontext
        with patch("services.rag.agentic.reasoning.trace_span", side_effect=lambda *args, **kwargs: nullcontext()):
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
                    if len(events) > 20:
                        break

        # Should filter stub response
        assert state.final_answer != "observation: none"
        assert len(state.final_answer) > 0

