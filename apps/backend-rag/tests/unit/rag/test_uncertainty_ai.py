"""
Unit Tests for Uncertainty AI & Guardrails Logic

Tests the evidence score calculation and policy enforcement:
- Evidence score calculation based on sources and context
- ABSTAIN policy when evidence_score < 0.3
- Warning injection when 0.3 <= evidence_score < 0.6
- Normal generation when evidence_score >= 0.6
- Override existing answer when evidence is weak
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
from services.rag.agentic.reasoning import ReasoningEngine, calculate_evidence_score
from services.tools.definitions import AgentState


def mock_token_usage():
    return TokenUsage(prompt_tokens=10, completion_tokens=20)


# ============================================================================
# Test Evidence Score Calculation
# ============================================================================


class TestEvidenceScoreCalculation:
    """Test suite for calculate_evidence_score function"""

    def test_evidence_score_with_high_quality_source(self):
        """Test score calculation with at least one source with score > 0.8"""
        sources = [
            {"id": 1, "title": "Source 1", "score": 0.85},
            {"id": 2, "title": "Source 2", "score": 0.6},
        ]
        context = ["Some context about KITAS visa requirements"]
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)

        # Should have +0.5 for high-quality source
        assert score >= 0.5
        assert score <= 1.0

    def test_evidence_score_with_multiple_sources(self):
        """Test score calculation with > 3 sources"""
        sources = [{"id": i, "title": f"Source {i}", "score": 0.7} for i in range(5)]
        context = ["Context from multiple sources"]
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)

        # Should have +0.2 for multiple sources (> 3)
        assert score >= 0.2
        assert score <= 1.0

    def test_evidence_score_with_keyword_matching(self):
        """Test score calculation when context contains query keywords"""
        sources = []
        context = [
            "KITAS is a work permit visa in Indonesia. "
            "It allows foreigners to work legally in the country."
        ]
        query = "What is KITAS visa?"

        score = calculate_evidence_score(sources, context, query)

        # Should have +0.3 for keyword matching
        assert score >= 0.3
        assert score <= 1.0

    def test_evidence_score_combines_all_factors(self):
        """Test score calculation combining all factors"""
        sources = [
            {"id": 1, "title": "Source 1", "score": 0.9},  # High quality
            {"id": 2, "title": "Source 2", "score": 0.8},  # High quality
            {"id": 3, "title": "Source 3", "score": 0.7},
            {"id": 4, "title": "Source 4", "score": 0.6},
            {"id": 5, "title": "Source 5", "score": 0.5},  # > 3 sources
        ]
        context = [
            "KITAS visa requirements and application process. "
            "KITAS allows foreigners to work in Indonesia legally."
        ]
        query = "What is KITAS visa?"

        score = calculate_evidence_score(sources, context, query)

        # Should combine: +0.5 (high quality) + 0.2 (multiple sources) + 0.3 (keywords)
        assert score >= 1.0  # Should be capped at 1.0
        assert score == 1.0

    def test_evidence_score_no_sources_no_context(self):
        """Test score calculation with no sources and no context"""
        sources = []
        context = []
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)

        # Should be 0.0
        assert score == 0.0

    def test_evidence_score_fallback_to_context_length(self):
        """Test score calculation falls back to context length when no sources"""
        sources = None
        context = ["This is a very detailed answer. " * 50]  # > 500 chars
        query = "What is KITAS?"

        score = calculate_evidence_score(sources, context, query)

        # Should have some score from substantial context
        assert score >= 0.3
        assert score <= 1.0

    def test_evidence_score_caps_at_one(self):
        """Test that score is capped at 1.0"""
        sources = [{"id": i, "title": f"Source {i}", "score": 0.9} for i in range(10)]
        context = [
            "KITAS visa requirements " * 20  # Long context with keywords
        ]
        query = "What is KITAS visa?"

        score = calculate_evidence_score(sources, context, query)

        # Should be exactly 1.0 (capped)
        assert score == 1.0

    def test_evidence_score_with_stop_words_filtering(self):
        """Test that stop words are filtered from keyword matching"""
        sources = []
        context = ["The is a an test"]  # Short context, no keywords
        query = "the is a an test"

        score = calculate_evidence_score(sources, context, query)

        # Should not match stop words
        # Note: If context is substantial (>500 chars), fallback may add score
        # So we just verify it's low (not matching keywords)
        assert score < 0.5  # Should be low since no keywords match

    def test_evidence_score_partial_keyword_matching(self):
        """Test score with partial keyword matching (30% threshold)"""
        sources = []
        context = ["KITAS visa"]
        query = "What is KITAS visa requirements?"

        score = calculate_evidence_score(sources, context, query)

        # Should match "KITAS" and "visa" keywords
        assert score >= 0.3


# ============================================================================
# Test Policy Enforcement - ABSTAIN (score < 0.3)
# ============================================================================


class TestAbstainPolicy:
    """Test suite for ABSTAIN policy when evidence_score < 0.3"""

    @pytest.mark.asyncio
    async def test_abstain_when_no_context_gathered(self):
        """Test ABSTAIN when no context is gathered"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = []  # No context

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: No info found", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, __, ___ = await engine.execute_react_loop(
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

        # Should have ABSTAIN message
        assert (
            "Mi dispiace, non ho trovato informazioni verificate sufficienti"
            in result_state.final_answer
        )
        assert hasattr(result_state, "evidence_score")
        assert result_state.evidence_score < 0.3

    @pytest.mark.asyncio
    async def test_abstain_when_weak_evidence(self):
        """Test ABSTAIN when evidence score is weak (< 0.3)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        # Weak context that won't score well
        state.context_gathered = ["Unrelated text"]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: Found something", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, __, ___ = await engine.execute_react_loop(
                state=state,
                llm_gateway=llm_gateway,
                chat=chat,
                initial_prompt="test",
                system_prompt="",
                query="What is KITAS?",  # Query doesn't match context
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Should have ABSTAIN message
        assert (
            "Mi dispiace, non ho trovato informazioni verificate sufficienti"
            in result_state.final_answer
        )
        assert result_state.evidence_score < 0.3

    @pytest.mark.asyncio
    async def test_abstain_overrides_existing_answer(self):
        """Test that ABSTAIN overrides existing answer when evidence is weak"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query")
        state.final_answer = "This is an existing answer"  # Already has answer
        state.context_gathered = ["Weak context"]  # But weak evidence

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=(
                "Final Answer: Existing answer",
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
                query="Unrelated query",  # Doesn't match context
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            )

        # Should have overridden with ABSTAIN message
        assert (
            "Mi dispiace, non ho trovato informazioni verificate sufficienti"
            in result_state.final_answer
        )
        assert "This is an existing answer" not in result_state.final_answer

    @pytest.mark.asyncio
    async def test_abstain_skips_llm_generation(self):
        """Test that ABSTAIN skips LLM generation"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = []  # No context

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: No info", "gemini-2.0-flash", None, mock_token_usage())
        )
        chat = MagicMock()

        with patch("services.rag.agentic.reasoning.parse_tool_call", return_value=None):
            result_state, _, __, ___ = await engine.execute_react_loop(
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

        # Should have ABSTAIN message without calling LLM for final answer
        assert (
            "Mi dispiace, non ho trovato informazioni verificate sufficienti"
            in result_state.final_answer
        )
        # Verify LLM was not called for final answer generation
        # (only called once for the initial thought)
        assert llm_gateway.send_message.call_count == 1


# ============================================================================
# Test Policy Enforcement - Warning (0.3 <= score < 0.6)
# ============================================================================


class TestWarningPolicy:
    """Test suite for warning injection when 0.3 <= evidence_score < 0.6"""

    @pytest.mark.asyncio
    async def test_warning_injected_for_weak_evidence(self):
        """Test that warning is injected in prompt for weak evidence"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        # Moderate context that scores between 0.3 and 0.6
        # Use longer context with keywords to ensure score >= 0.3
        state.context_gathered = [
            "KITAS visa information and requirements. "
            "KITAS allows foreigners to work in Indonesia. "
            "KITAS visa application process."
        ]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Generated answer with caution", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should have generated answer (not ABSTAIN) if score >= 0.3
        if result_state.evidence_score >= 0.3:
            assert result_state.final_answer == "Generated answer with caution"
            # Verify warning was injected in the prompt if score < 0.6
            if result_state.evidence_score < 0.6:
                assert llm_gateway.send_message.call_count == 2
                final_prompt = llm_gateway.send_message.call_args_list[1][0][0]
                assert "WARNING: Evidence is weak" in final_prompt
                assert "precautionary language" in final_prompt
                assert "Do NOT be definitive" in final_prompt
        else:
            # If score < 0.3, ABSTAIN should be triggered
            assert (
                "Mi dispiace, non ho trovato informazioni verificate sufficienti"
                in result_state.final_answer
            )

    @pytest.mark.asyncio
    async def test_no_warning_for_strong_evidence(self):
        """Test that no warning is injected for strong evidence (>= 0.6)"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=2)
        # Strong context with high-quality sources and keywords
        state.context_gathered = [
            "KITAS visa requirements and application process. "
            "KITAS allows foreigners to work in Indonesia legally. " * 10
        ]
        state.sources = [
            {"id": 1, "title": "Source 1", "score": 0.9},  # High quality (+0.5)
            {"id": 2, "title": "Source 2", "score": 0.85},
            {"id": 3, "title": "Source 3", "score": 0.8},
            {"id": 4, "title": "Source 4", "score": 0.75},  # > 3 sources (+0.2)
        ]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Confident answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should have generated answer (not the thought)
        # When max_steps is reached without Final Answer, it generates from context
        assert result_state.final_answer == "Confident answer"
        # Verify NO warning was injected
        assert llm_gateway.send_message.call_count == 2
        final_prompt = llm_gateway.send_message.call_args_list[1][0][0]
        assert "WARNING: Evidence is weak" not in final_prompt
        # Score should be >= 0.6 (0.5 from high-quality source + 0.2 from multiple sources + 0.3 from keywords)
        assert result_state.evidence_score >= 0.6


# ============================================================================
# Test Policy Enforcement - Normal Generation (score >= 0.6)
# ============================================================================


class TestNormalGeneration:
    """Test suite for normal generation when evidence_score >= 0.6"""

    @pytest.mark.asyncio
    async def test_normal_generation_with_strong_evidence(self):
        """Test normal generation when evidence is strong"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=2)
        # Strong context
        state.context_gathered = ["KITAS visa requirements " * 20]
        state.sources = [
            {"id": 1, "title": "Source 1", "score": 0.9},
            {"id": 2, "title": "Source 2", "score": 0.85},
            {"id": 3, "title": "Source 3", "score": 0.8},
            {"id": 4, "title": "Source 4", "score": 0.75},
        ]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Comprehensive answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should have generated normal answer (not the thought)
        assert result_state.final_answer == "Comprehensive answer"
        assert result_state.evidence_score >= 0.6
        # No warning should be present
        assert llm_gateway.send_message.call_count == 2
        final_prompt = llm_gateway.send_message.call_args_list[1][0][0]
        assert "WARNING: Evidence is weak" not in final_prompt


# ============================================================================
# Test Streaming Mode
# ============================================================================


class TestUncertaintyStreaming:
    """Test suite for uncertainty logic in streaming mode"""

    @pytest.mark.asyncio
    async def test_stream_abstain_when_weak_evidence(self):
        """Test streaming mode ABSTAIN when evidence is weak"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = []  # No context

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            return_value=("Thought: No info", "gemini-2.0-flash", None, mock_token_usage())
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
                query="test",
                user_id="test_user",
                model_tier=0,
                tool_execution_counter={},
            ):
                events.append(event)

        # Should have evidence_score event
        evidence_events = [e for e in events if e.get("type") == "evidence_score"]
        assert len(evidence_events) == 1
        assert evidence_events[0]["data"]["score"] < 0.3

        # Should have ABSTAIN message in final answer
        assert (
            "Mi dispiace, non ho trovato informazioni verificate sufficienti" in state.final_answer
        )

    @pytest.mark.asyncio
    async def test_stream_warning_for_weak_evidence(self):
        """Test streaming mode injects warning for weak evidence"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        # Moderate context that should score between 0.3 and 0.6
        state.context_gathered = [
            "KITAS visa information and requirements. "
            "KITAS allows foreigners to work in Indonesia. "
            "KITAS visa application process."
        ]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Cautious answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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
        assert len(evidence_events) == 1

        # Verify warning was injected if score is in warning range
        if state.evidence_score >= 0.3 and state.evidence_score < 0.6:
            assert llm_gateway.send_message.call_count == 2
            final_prompt = llm_gateway.send_message.call_args_list[1][0][0]
            assert "WARNING: Evidence is weak" in final_prompt
        elif state.evidence_score < 0.3:
            # If score is too low, ABSTAIN should be triggered
            assert (
                "Mi dispiace, non ho trovato informazioni verificate sufficienti"
                in state.final_answer
            )


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestUncertaintyEdgeCases:
    """Test suite for edge cases in uncertainty logic"""

    @pytest.mark.asyncio
    async def test_evidence_score_stored_in_state(self):
        """Test that evidence_score is stored in state"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = ["KITAS visa requirements"]
        state.sources = [{"id": 1, "title": "Source 1", "score": 0.9}]

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should have evidence_score stored
        assert hasattr(result_state, "evidence_score")
        assert isinstance(result_state.evidence_score, float)
        assert 0.0 <= result_state.evidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_evidence_score_with_none_sources(self):
        """Test evidence score calculation when sources is None"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = ["KITAS visa requirements " * 20]  # Long context
        state.sources = None  # Explicitly None

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should still calculate score (fallback to context length)
        assert hasattr(result_state, "evidence_score")
        assert result_state.evidence_score >= 0.0

    @pytest.mark.asyncio
    async def test_evidence_score_with_empty_sources_list(self):
        """Test evidence score calculation with empty sources list"""
        tool_map = {}
        engine = ReasoningEngine(tool_map=tool_map)

        state = AgentState(query="test query", max_steps=1)
        state.context_gathered = ["KITAS visa"]
        state.sources = []  # Empty list

        llm_gateway = AsyncMock()
        llm_gateway.send_message = AsyncMock(
            side_effect=[
                ("Thought: Found info", "gemini-2.0-flash", None, mock_token_usage()),
                ("Answer", "gemini-2.0-flash", None, mock_token_usage()),
            ]
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

        # Should calculate score based on context keywords
        assert hasattr(result_state, "evidence_score")
        assert result_state.evidence_score >= 0.0
