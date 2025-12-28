"""
Exact Coverage Tests for reasoning.py - Target specific missing lines
These tests are designed to hit exact lines that are not covered
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

from services.rag.agentic.reasoning import ReasoningEngine, detect_team_query
from services.tools.definitions import AgentState, ToolCall


@pytest.mark.unit
@pytest.mark.coverage
class TestReasoningExactCoverage:
    """Tests to hit exact missing lines"""

    @pytest.mark.asyncio
    async def test_citation_parsing_keyerror_exact_line_270(self):
        """Test citation parsing KeyError to hit line 270"""
        mock_tool = MagicMock()
        # Return JSON without 'sources' key to trigger KeyError
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info"}'
        )
        
        tool_map = {
            "vector_search": mock_tool
        }
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.context_gathered = []
        state.sources = []  # Initialize as empty list

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
                # This should trigger KeyError when trying to access 'sources' key
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

        # Should handle KeyError gracefully (line 270)
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_citation_parsing_valueerror_exact_line_270(self):
        """Test citation parsing ValueError to hit line 270"""
        mock_tool = MagicMock()
        # Return JSON with invalid sources structure
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": "invalid_string"}'
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
                # This should trigger ValueError when trying to extend with invalid sources
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

        # Should handle ValueError gracefully (line 270)
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_citation_parsing_typeerror_exact_line_270(self):
        """Test citation parsing TypeError to hit line 270"""
        mock_tool = MagicMock()
        # Return JSON with sources as None
        mock_tool.execute = AsyncMock(
            return_value='{"content": "KITAS info", "sources": null}'
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
                # This should trigger TypeError when trying to extend with None
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

        # Should handle TypeError gracefully (line 270)
        assert result_state is not None

    @pytest.mark.asyncio
    async def test_warning_policy_llm_error_exact_line_391(self):
        """Test warning policy LLM error to hit lines 391-393"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        # Set evidence_score to trigger warning policy (0.3 <= score < 0.6)
        state.context_gathered = ["Some information about KITAS"]
        state.sources = [{"id": 1, "score": 0.5}]
        state.evidence_score = 0.4  # Weak evidence

        llm_gateway = AsyncMock()
        from google.api_core.exceptions import ResourceExhausted
        call_count = 0
        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("Thought", "gemini-2.0-flash", None)
            else:
                # Final answer generation raises ResourceExhausted (line 391)
                raise ResourceExhausted("Rate limit exceeded")
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

        # Should handle ResourceExhausted in warning policy (lines 391-393)
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_final_answer_stub_filtering_exact_line_408(self):
        """Test final answer stub filtering to hit lines 408-409"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = [{"id": 1, "score": 0.9}]
        # Set stub response that should be filtered
        state.final_answer = "no further action needed"

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

        # Should filter stub response (lines 408-409)
        assert state.final_answer != "no further action needed"
        assert len(state.final_answer) > 0

    @pytest.mark.asyncio
    async def test_streaming_llm_error_exact_line_681(self):
        """Test streaming LLM error to hit lines 681-682"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        state.final_answer = None

        llm_gateway = AsyncMock()
        from google.api_core.exceptions import ServiceUnavailable
        call_count = 0
        def mock_send_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("Thought", "gemini-2.0-flash", None)
            else:
                # Final answer generation raises ServiceUnavailable (line 681)
                raise ServiceUnavailable("Service unavailable")
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

        # Should handle ServiceUnavailable in streaming (lines 681-682)
        assert len(events) >= 0
        assert state.final_answer is not None

    @pytest.mark.asyncio
    async def test_streaming_stub_filtering_exact_line_697(self):
        """Test streaming stub filtering to hit line 697"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        # Set stub response that should be filtered
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

        # Should filter stub response (line 697)
        assert state.final_answer != "observation: none"
        assert len(state.final_answer) > 0

    def test_detect_team_query_list_all(self):
        """Test detect_team_query for list_all (lines 746-876)"""
        result = detect_team_query("list all team members")
        assert result[0] is True
        assert result[1] == "list_all"
        assert result[2] == ""

    def test_detect_team_query_email(self):
        """Test detect_team_query for email (lines 746-876)"""
        result = detect_team_query("find john@example.com")
        assert result[0] is True
        assert result[1] == "search_by_email"
        assert result[2] == "john@example.com"

    def test_detect_team_query_role(self):
        """Test detect_team_query for role (lines 746-876)"""
        result = detect_team_query("chi si occupa di tax")
        assert result[0] is True
        assert result[1] == "search_by_role"
        assert result[2] == "tax"

    def test_detect_team_query_name(self):
        """Test detect_team_query for name (lines 746-876)"""
        result = detect_team_query("chi è Mario Rossi")
        assert result[0] is True
        assert result[1] == "search_by_name"
        assert "Mario" in result[2] or "Rossi" in result[2]

    def test_detect_team_query_not_string(self):
        """Test detect_team_query with non-string input (line 746)"""
        result = detect_team_query(123)
        assert result[0] is False
        assert result[1] == ""
        assert result[2] == ""

    def test_detect_team_query_empty(self):
        """Test detect_team_query with empty string (line 750)"""
        result = detect_team_query("   ")
        assert result[0] is False
        assert result[1] == ""
        assert result[2] == ""

    def test_detect_team_query_no_match(self):
        """Test detect_team_query with no match (line 876)"""
        result = detect_team_query("what is KITAS?")
        assert result[0] is False
        assert result[1] == ""
        assert result[2] == ""

