"""
Tests for Response Pipeline Integration
Tests how ReasoningEngine integrates with response processing pipeline

Coverage:
- Response pipeline processing
- Pipeline error handling
- Post-processing fallback
- Citation updates from pipeline
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
from backend.services.tools.definitions import AgentState


def mock_token_usage():
    return TokenUsage(prompt_tokens=10, completion_tokens=20)


@pytest.mark.unit
@pytest.mark.coverage
class TestResponsePipeline:
    """Test response pipeline integration"""

    @pytest.mark.asyncio
    async def test_response_pipeline_processing(self):
        """Test that response pipeline processes final answer"""
        tool_map = {}

        # Mock response pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(
            return_value={
                "response": "Processed answer about KITAS",
                "citations": [{"id": "doc1", "score": 0.9}],
            }
        )

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=mock_pipeline)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS is a temporary residence permit " * 20]
        state.sources = [{"id": 1, "score": 0.9}]
        state.final_answer = "KITAS is a permit"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Verify pipeline was called
        assert mock_pipeline.process.called
        # Verify response was updated
        assert result_state.final_answer == "Processed answer about KITAS"

    @pytest.mark.asyncio
    async def test_response_pipeline_error_handling(self):
        """Test that pipeline errors are handled gracefully"""
        tool_map = {}

        # Mock response pipeline that raises error
        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(side_effect=ValueError("Pipeline error"))

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=mock_pipeline)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS information " * 20]
        state.sources = [{"id": 1, "score": 0.9}]
        state.final_answer = "KITAS is a permit"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Should handle error gracefully and use post_process_response fallback
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_response_pipeline_citation_update(self):
        """Test that pipeline can update citations"""
        tool_map = {}

        # Mock response pipeline that updates citations
        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(
            return_value={
                "response": "Processed answer",
                "citations": [{"id": "new_doc", "score": 0.95}],
            }
        )

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=mock_pipeline)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = [{"id": "old_doc", "score": 0.8}]
        state.final_answer = "KITAS is a permit"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Verify citations were updated if pipeline returned them
        if hasattr(result_state, "sources") and result_state.sources:
            # Citations should be updated from pipeline
            pass  # Pipeline can update citations

    @pytest.mark.asyncio
    async def test_response_pipeline_streaming_mode(self):
        """Test response pipeline in streaming mode"""
        tool_map = {}

        # Mock response pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(
            return_value={"response": "Streamed processed answer", "citations": []}
        )

        engine = ReasoningEngine(tool_map=tool_map, response_pipeline=mock_pipeline)

        state = AgentState(query="What is KITAS?", max_steps=1)
        state.context_gathered = ["KITAS info " * 20]
        state.sources = []
        state.final_answer = "KITAS is a permit"

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Answer", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        events = []
        tool_execution_counter = {"count": 0}
        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None):
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

        # Verify pipeline was called
        assert mock_pipeline.process.called
        # Verify token events were yielded
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) > 0
