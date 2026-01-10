"""
Integration Tests for ReasoningEngine Full Flow
Tests complete request flows from query to final answer

Coverage:
- Full ReAct loop execution
- Tool execution with real-like scenarios
- Evidence score calculation in context
- Policy enforcement (ABSTAIN/Warning)
- Final answer generation
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
class TestReasoningFullFlow:
    """Integration tests for complete reasoning flows"""

    @pytest.mark.asyncio
    async def test_full_flow_with_vector_search_and_answer(self):
        """Test complete flow: query -> tool call -> context -> answer"""
        # Mock vector_search tool
        mock_vector_search = MagicMock()
        mock_vector_search.execute = AsyncMock(
            return_value='{"content": "KITAS is a temporary residence permit for Indonesia", "sources": [{"id": "doc1", "score": 0.9}]}'
        )

        tool_map = {"vector_search": mock_vector_search}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=5)
        state.context_gathered = []
        state.sources = []

        llm_gateway = AsyncMock()
        call_count = 0

        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (
                    "Thought: I need to search for KITAS. Action: vector_search('KITAS')",
                    "gemini-2.0-flash",
                    None,
                )
            else:
                return (
                    "Final Answer: KITAS is a temporary residence permit for Indonesia",
                    "gemini-2.0-flash",
                    None,
                )

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
            "backend.services.rag.agentic.reasoning.trace_span",
            side_effect=lambda *args, **kwargs: nullcontext(),
        ):
            with patch(
                "backend.services.rag.agentic.reasoning.parse_tool_call", return_value=mock_tool_call
            ):
                result_state, model_used, messages = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="You are a helpful assistant. Answer the user's question about KITAS.",
                    system_prompt="You are a helpful assistant.",
                    query="What is KITAS?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter=tool_execution_counter,
                )

        # Verify complete flow
        assert result_state.final_answer is not None
        assert len(result_state.context_gathered) > 0
        assert len(result_state.steps) > 0
        assert result_state.evidence_score >= 0.0
        assert mock_vector_search.execute.called

    @pytest.mark.asyncio
    async def test_full_flow_abstain_with_no_context(self):
        """Test complete flow that triggers ABSTAIN policy"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is XYZ123?", max_steps=2)
        state.context_gathered = []  # No context
        state.sources = []

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Thought: I don't have information about XYZ123",
                "gemini-2.0-flash",
                None,
            )
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is XYZ123?",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter=tool_execution_counter,
            )

        # Should trigger ABSTAIN
        assert result_state.final_answer is not None
        assert (
            "non ho trovato informazioni" in result_state.final_answer.lower()
            or "dispiace" in result_state.final_answer.lower()
        )
        assert result_state.evidence_score < 0.3

    @pytest.mark.asyncio
    async def test_full_flow_warning_with_weak_evidence(self):
        """Test complete flow that triggers warning policy"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        # Weak evidence: some context but not strong
        state.context_gathered = ["Some information about KITAS"]
        state.sources = [{"id": 1, "score": 0.5}]  # Low score

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought", "gemini-2.0-flash", None),
                ("Based on limited information, KITAS might be a permit", "gemini-2.0-flash", None),
            ]
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should have warning injected if score is in warning range
        assert result_state.final_answer is not None
        if 0.3 <= result_state.evidence_score < 0.6:
            # Verify warning was injected
            assert llm_gateway.send_message.call_count >= 2
            final_prompt = llm_gateway.send_message.call_args_list[-1][0][0]
            assert "WARNING: Evidence is weak" in final_prompt
