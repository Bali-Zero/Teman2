"""
Unit Tests for ReasoningEngine - ReAct Loop Implementation

Tests the core reasoning engine that executes the ReAct pattern:
- Thought → Action → Observation → Repeat
- Tool call parsing (native + regex fallback)
- Citation handling
- Early exit optimization
- Final answer generation
- Pipeline processing and self-correction
"""

import json
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

from google.api_core.exceptions import ResourceExhausted

from services.rag.agentic.reasoning import ReasoningEngine
from services.tools.definitions import AgentState, ToolCall

# ============================================================================
# Test ReasoningEngine Initialization
# ============================================================================


class TestReasoningEngineInitialization:
    """Test suite for ReasoningEngine initialization"""

    def test_reasoning_engine_initializes_successfully(self):
        """Test that ReasoningEngine initializes with required parameters"""
        tool_map = {"vector_search": MagicMock()}
        response_pipeline = MagicMock()

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=response_pipeline)

        assert engine.tool_map == tool_map
        assert engine.response_pipeline == response_pipeline

    def test_reasoning_engine_initializes_without_pipeline(self):
        """Test that ReasoningEngine works without response pipeline"""
        tool_map = {"vector_search": MagicMock()}

        engine = ReasoningEngine(tool_map=tool_map)

        assert engine.tool_map == tool_map
        assert engine.response_pipeline is None


# ============================================================================
# Test ReAct Loop Execution
# ============================================================================


class TestReActLoopExecution:
    """Test suite for execute_react_loop method"""

    @pytest.mark.asyncio
    async def test_execute_react_loop_single_step_with_final_answer(self):
        """Test ReAct loop completes in one step when final answer provided"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")
        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: This is the answer", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        result_state, model_name, messages = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gateway,
            chat=chat,
            initial_prompt="What is 2+2?",
            system_prompt="You are helpful",
            query="What is 2+2?",
            user_id="test_user",
            model_tier=0,
            tool_execution_counter={},
        )

        assert result_state.final_answer == "This is the answer"
        assert result_state.current_step == 1
        assert len(result_state.steps) == 1
        assert result_state.steps[0].is_final is True
        assert model_name == "gemini-2.0-flash"
        assert len(messages) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_execute_react_loop_with_tool_call(self):
        """Test ReAct loop executes tool and processes observation"""
        tool_mock = MagicMock()
        tool_mock.execute = AsyncMock(return_value="Tool result: 42")
        tool_map = {"calculator": tool_mock}

        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        # First call: tool call, Second call: final answer
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                (
                    "Thought: Need to calculate\nAction: calculator\nInput: 2+2",
                    "gemini-2.0-flash",
                    None,
                ),
                (
                    "Final Answer: Based on the calculation, the answer is 42",
                    "gemini-2.0-flash",
                    None,
                ),
            ]
        )
        chat = MagicMock()

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            side_effect=[
                ToolCall(
                    tool_name="calculator", arguments={"input": "2+2"}
                ),  # First call returns tool
                None,  # Second call returns None (so it parses final answer)
            ],
        ):
            with patch(
                "services.rag.agentic.reasoning.execute_tool", return_value="Tool result: 42"
            ):
                result_state, model_name, messages = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="What is 2+2?",
                    system_prompt="You are helpful",
                    query="What is 2+2?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        assert result_state.final_answer == "Based on the calculation, the answer is 42"
        assert result_state.current_step == 2
        assert len(result_state.steps) == 2
        assert result_state.steps[0].action.tool_name == "calculator"
        assert result_state.steps[0].observation == "Tool result: 42"

    @pytest.mark.asyncio
    async def test_execute_react_loop_early_exit_on_vector_search(self):
        """Test early exit when vector_search returns sufficient context"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Search for info", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        # Simulate vector_search returning rich content (> 500 chars)
        rich_content = "This is a very detailed answer. " * 50  # > 500 chars

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            return_value=ToolCall(tool_name="vector_search", arguments={"query": "test"}),
        ):
            with patch("services.rag.agentic.reasoning.execute_tool", return_value=rich_content):
                result_state, model_name, messages = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="What is KITAS?",
                    system_prompt="You are helpful",
                    query="What is KITAS?",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        # Should early exit after first step
        assert result_state.current_step == 1
        assert len(result_state.steps) == 1
        assert result_state.steps[0].action.tool_name == "vector_search"

    @pytest.mark.asyncio
    async def test_execute_react_loop_max_steps_reached(self):
        """Test that loop stops at max_steps"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=2)

        llm_gateway = AsyncMock()
        # Never provide final answer
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Still thinking...", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, model_name, messages = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="Complex query",
                system_prompt="You are helpful",
                query="Complex query",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Should stop at max_steps
        assert result_state.current_step == 2
        assert len(result_state.steps) == 2


# ============================================================================
# Test Tool Call Parsing
# ============================================================================


class TestToolCallParsing:
    """Test suite for tool call parsing (native + regex)"""

    @pytest.mark.asyncio
    async def test_native_function_call_detected(self):
        """Test that native function calls from Gemini are detected"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        # Mock response with native function call
        response_obj = MagicMock()
        candidate = MagicMock()
        part = MagicMock()

        response_obj.candidates = [candidate]
        candidate.content.parts = [part]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("", "gemini-2.0-flash", response_obj),  # First call with native function call
                ("Final Answer: Done", "gemini-2.0-flash", None),  # Second call with final answer
            ]
        )
        chat = MagicMock()

        tool_call = ToolCall(tool_name="vector_search", arguments={"query": "test"})

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            side_effect=[
                tool_call,
                None,
                None,
            ],  # First iteration: native returns tool_call, Second iteration: both return None
        ):
            with patch("services.rag.agentic.reasoning.execute_tool", return_value="result"):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="test",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        # Should have detected the native function call
        assert result_state.current_step >= 1


# ============================================================================
# Test Citation Handling
# ============================================================================


class TestCitationHandling:
    """Test suite for citation handling from vector_search"""

    @pytest.mark.asyncio
    async def test_citation_extraction_from_vector_search(self):
        """Test that citations are extracted from vector_search results"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Search", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        # Simulate vector_search returning JSON with sources
        # Content needs to be > 500 chars to trigger early exit
        long_content = "This is detailed content about KITAS visas. " * 20  # Make it > 500 chars
        vector_result = json.dumps(
            {
                "content": long_content,
                "sources": [
                    {"title": "Source 1", "url": "http://example.com/1"},
                    {"title": "Source 2", "url": "http://example.com/2"},
                ],
            }
        )

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            return_value=ToolCall(tool_name="vector_search", arguments={"query": "test"}),
        ):
            with patch("services.rag.agentic.reasoning.execute_tool", return_value=vector_result):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="test",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        # Should have extracted sources (only once due to early exit)
        assert hasattr(result_state, "sources")
        assert len(result_state.sources) == 2
        assert result_state.sources[0]["title"] == "Source 1"

    @pytest.mark.asyncio
    async def test_citation_handles_invalid_json(self):
        """Test that invalid JSON doesn't crash citation handling"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Search", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        # Invalid JSON
        vector_result = "This is not JSON"

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            return_value=ToolCall(tool_name="vector_search", arguments={"query": "test"}),
        ):
            with patch("services.rag.agentic.reasoning.execute_tool", return_value=vector_result):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="test",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        # Should not crash, just use raw result
        assert result_state.steps[0].observation == "This is not JSON"


# ============================================================================
# Test Final Answer Generation
# ============================================================================


class TestFinalAnswerGeneration:
    """Test suite for final answer generation"""

    @pytest.mark.asyncio
    async def test_final_answer_generated_from_context(self):
        """Test that final answer is generated when not provided"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)

        llm_gateway = AsyncMock()
        # First call: tool execution (adds to context), Second call: generate final answer from context
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Search for info", "gemini-2.0-flash", None),
                ("Generated final answer based on context", "gemini-2.0-flash", None),
            ]
        )
        chat = MagicMock()

        with patch(
            "services.rag.agentic.reasoning.parse_tool_call",
            return_value=ToolCall(tool_name="vector_search", arguments={"query": "test"}),
        ):
            with patch(
                "services.rag.agentic.reasoning.execute_tool", return_value="Context from tool"
            ):
                result_state, _, _ = await engine.execute_react_loop(
                    state=state,
                    llm_gateway=llm_gateway,
                    chat=chat,
                    initial_prompt="test",
                    system_prompt="",
                    query="test",
                    user_id="test_user",
                    model_tier=0,
                    tool_execution_counter={},
                )

        # Should have generated final answer from gathered context
        assert result_state.final_answer == "Generated final answer based on context"
        assert len(result_state.context_gathered) > 0

    @pytest.mark.asyncio
    async def test_stub_response_detection(self):
        """Test that stub responses are replaced with fallback"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: No further action needed", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        result_state, _, _ = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gateway,
            chat=chat,
            initial_prompt="test",
            system_prompt="",
            query="test",
            user_id="test_user",
            model_tier=0,
            tool_execution_counter={},
        )

        # Stub response should be replaced
        assert "Mi dispiace" in result_state.final_answer


# ============================================================================
# Test Pipeline Processing
# ============================================================================


class TestPipelineProcessing:
    """Test suite for response pipeline processing"""

    @pytest.mark.asyncio
    async def test_pipeline_processes_final_answer(self):
        """Test that pipeline processes the final answer"""
        tool_map = {}
        response_pipeline = AsyncMock()
        response_pipeline.process = AsyncMock(
            return_value={
                "response": "Processed answer",
                "verification_status": "verified",
                "citation_count": 2,
            }
        )

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=response_pipeline)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: Raw answer", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        result_state, _, _ = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gateway,
            chat=chat,
            initial_prompt="test",
            system_prompt="",
            query="test",
            user_id="test_user",
            model_tier=0,
            tool_execution_counter={},
        )

        # Pipeline should have been called
        response_pipeline.process.assert_called_once()
        # Final answer should be processed version
        assert result_state.final_answer == "Processed answer"

    @pytest.mark.asyncio
    async def test_self_correction_on_low_verification_score(self):
        """Test that self-correction is triggered on low verification score"""
        tool_map = {}
        response_pipeline = AsyncMock()
        # First process: low score, Second process: high score
        response_pipeline.process = AsyncMock(
            side_effect=[
                {
                    "response": "Bad answer",
                    "verification_score": 0.5,
                    "verification": {"score": 0.5, "reasoning": "Insufficient evidence"},
                },
                {
                    "response": "Corrected answer",
                    "verification_score": 0.9,
                    "verification_status": "verified",
                },
            ]
        )

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=response_pipeline)

        state = AgentState(query="test query")
        state.context_gathered = ["Some context"]

        llm_gateway = AsyncMock()
        # First: final answer, Second: corrected answer
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Final Answer: Initial answer", "gemini-2.0-flash", None),
                ("Corrected answer after review", "gemini-2.0-flash", None),
            ]
        )
        chat = MagicMock()

        result_state, _, _ = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gateway,
            chat=chat,
            initial_prompt="test",
            system_prompt="",
            query="test",
            user_id="test_user",
            model_tier=0,
            tool_execution_counter={},
        )

        # Pipeline should have been called twice (initial + correction)
        assert response_pipeline.process.call_count == 2
        # Final answer should be corrected version
        assert result_state.final_answer == "Corrected answer"


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test suite for error handling in ReAct loop"""

    @pytest.mark.asyncio
    async def test_loop_breaks_on_llm_error(self):
        """Test that loop breaks gracefully on LLM errors"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(side_effect=ResourceExhausted("Quota exceeded"))
        chat = MagicMock()

        result_state, _, _ = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gateway,
            chat=chat,
            initial_prompt="test",
            system_prompt="",
            query="test",
            user_id="test_user",
            model_tier=0,
            tool_execution_counter={},
        )

        # Should have exited early with no steps
        assert result_state.current_step == 1
        assert len(result_state.steps) == 0

    @pytest.mark.asyncio
    async def test_pipeline_error_falls_back_to_basic_processing(self):
        """Test that pipeline errors trigger fallback to basic post-processing"""
        tool_map = {}
        response_pipeline = AsyncMock()
        response_pipeline.process = AsyncMock(side_effect=ValueError("Pipeline error"))

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=response_pipeline)

        state = AgentState(query="test query")

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Final Answer: Raw answer", "gemini-2.0-flash", None)
        )
        chat = MagicMock()

        with patch(
            "services.rag.agentic.reasoning.post_process_response",
            return_value="Fallback processed",
        ):
            result_state, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="test",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Should have used fallback processing
        assert result_state.final_answer == "Fallback processed"
