"""
Comprehensive unit tests for backend/services/rag/agentic/reasoning.py
Covers: _validate_context_quality, ReasoningEngine (localized stubs,
        trusted tools check, evidence scoring, ABSTAIN logic, Tier 1 fallback,
        ReAct loop execution).
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.tools.definitions import AgentState, AgentStep, ToolCall


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_tracing():
    """Disable tracing for all tests."""
    with patch("backend.services.rag.agentic.reasoning.trace_span") as ts, \
         patch("backend.services.rag.agentic.reasoning.set_span_attribute"), \
         patch("backend.services.rag.agentic.reasoning.set_span_status"), \
         patch("backend.services.rag.agentic.reasoning.add_span_event"):
        ts.return_value.__enter__ = MagicMock()
        ts.return_value.__exit__ = MagicMock(return_value=False)
        yield


@pytest.fixture(autouse=True)
def _patch_metrics():
    """Stub all Prometheus counters / histograms imported at module level."""
    metrics = [
        "abstain_decision_total",
        "strict_abstain_critical_total",
        "tier1_fallback_activated_total",
        "tier1_fallback_failed_total",
        "tier1_fallback_success_total",
        "tier1_response_duration",
    ]
    patches = {}
    for m in metrics:
        p = patch(f"backend.services.rag.agentic.reasoning.{m}", MagicMock())
        patches[m] = p.start()
    yield patches
    for p in patches.values():
        try:
            p.stop()  # type: ignore[arg-type]
        except Exception:
            pass
    patch.stopall()


@pytest.fixture
def engine():
    """Basic ReasoningEngine with empty tool_map."""
    from backend.services.rag.agentic.reasoning import ReasoningEngine
    return ReasoningEngine(tool_map={}, response_pipeline=None)


# ============================================================================
# _validate_context_quality (module-level function)
# ============================================================================

class TestValidateContextQuality:

    def test_empty_context_returns_zero(self, engine):
        assert engine._validate_context_quality("hello", []) == 0.0

    def test_single_matching_item(self, engine):
        score = engine._validate_context_quality("visa kitas", ["visa kitas procedure"])
        assert score > 0.0

    def test_no_keyword_match(self, engine):
        score = engine._validate_context_quality("xyz123", ["completely unrelated text"])
        # Count penalty contributes, keyword match is zero
        assert score >= 0.0
        assert score < 0.5

    def test_multiple_items_boost_score(self, engine):
        items = [f"visa requirement number {i}" for i in range(5)]
        score = engine._validate_context_quality("visa requirement", items)
        assert score > 0.0

    def test_score_capped_at_max(self, engine):
        items = ["visa visa visa visa visa"] * 10
        score = engine._validate_context_quality("visa", items)
        assert score <= 1.0


# ============================================================================
# _get_localized_stub
# ============================================================================

class TestLocalizedStub:

    def test_italian_abstain(self, engine):
        result = engine._get_localized_stub("abstain", "ITALIAN")
        assert "Mi dispiace" in result

    def test_english_abstain(self, engine):
        result = engine._get_localized_stub("abstain", "ENGLISH")
        assert "I'm sorry" in result

    def test_indonesian_abstain(self, engine):
        result = engine._get_localized_stub("abstain", "INDONESIAN")
        assert "Maaf" in result

    def test_unknown_language_falls_back_to_english(self, engine):
        result = engine._get_localized_stub("abstain", "KLINGON")
        assert "sorry" in result.lower()

    def test_unknown_key_falls_back(self, engine):
        result = engine._get_localized_stub("nonexistent_key", "ENGLISH")
        assert "sorry" in result.lower()

    def test_abstain_detailed_english(self, engine):
        result = engine._get_localized_stub("abstain_detailed", "ENGLISH")
        assert "I can help you with" in result

    def test_error_stub(self, engine):
        result = engine._get_localized_stub("error", "ITALIAN")
        assert "Riprova" in result

    def test_confused_stub(self, engine):
        result = engine._get_localized_stub("confused", "ENGLISH")
        assert "rephrase" in result


# ============================================================================
# Trusted Tools check
# ============================================================================

class TestTrustedToolsCheck:

    @pytest.mark.asyncio
    async def test_trusted_tool_bypasses_evidence_scoring(self, engine):
        """When a trusted tool (e.g. get_pricing) has output, evidence = 0.85."""
        state = AgentState(query="quanto costa KITAS?", max_steps=1, current_step=0)
        tool_call = ToolCall(tool_name="get_pricing", arguments={"service_type": "visa"})
        tool_call.result = "Price: Rp 10.000.000 for KITAS"
        tool_call.execution_time = 0.5
        step = AgentStep(
            step_number=1,
            thought="Let me check pricing",
            action=tool_call,
            observation="Price: Rp 10.000.000 for KITAS, includes permit processing",
        )
        state.steps.append(step)
        state.final_answer = "The KITAS costs Rp 10.000.000"
        state.context_gathered = ["Price: Rp 10.000.000"]

        # Mock dependencies
        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        mock_chat = MagicMock()

        from backend.services.llm_clients.pricing import TokenUsage

        # Simulate the engine already having run the loop (we just test post-loop logic)
        # We patch execute_react_loop internals
        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):

            # We need to mock the LLM call to simulate the loop
            mock_gateway.send_message = AsyncMock(return_value=(
                "Final Answer: The KITAS costs Rp 10.000.000",
                "gemini-flash",
                MagicMock(candidates=[]),
                TokenUsage(),
            ))

            result_state, model_name, msgs, usage = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=mock_chat,
                initial_prompt="How much does KITAS cost?",
                system_prompt="You are Zantara",
                query="quanto costa KITAS?",
                user_id="user1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            # trusted_tools_used should be True since get_pricing was used with substantial output
            assert result_state.trusted_tools_used is True


    @pytest.mark.asyncio
    async def test_trusted_tool_with_error_observation_not_trusted(self, engine):
        """If trusted tool returns an error, it should NOT be trusted."""
        state = AgentState(query="price?", max_steps=1, current_step=0)
        tool_call = ToolCall(tool_name="get_pricing", arguments={})
        tool_call.result = "Error: service unavailable"
        tool_call.execution_time = 0.1
        step = AgentStep(
            step_number=1,
            thought="check price",
            action=tool_call,
            observation="Error: service unavailable",
        )
        state.steps.append(step)
        state.final_answer = "Could not get pricing"

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: Could not get pricing",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="price?",
                system_prompt="system",
                query="price?",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            # "error" in observation → not trusted
            assert result_state.trusted_tools_used is False


# ============================================================================
# Evidence scoring & ABSTAIN logic
# ============================================================================

class TestEvidenceScoring:

    @pytest.mark.asyncio
    async def test_low_evidence_critical_domain_strict_abstain(self, engine):
        """Critical domain + low evidence → strict ABSTAIN."""
        state = AgentState(query="what visa do I need?", max_steps=1, current_step=0)
        state.final_answer = "You need a B211"
        state.skip_rag = False

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: You need a B211",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=True), \
             patch("backend.services.rag.agentic.reasoning.get_critical_domain_type", return_value="visa"), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="visa?",
                system_prompt="sys",
                query="what visa do I need?",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            # ABSTAIN should override the original answer
            assert "I can help you with" in result_state.final_answer or "informazioni verificate" in result_state.final_answer

    @pytest.mark.asyncio
    async def test_pricing_data_in_answer_trusts_output(self, engine):
        """If final_answer contains pricing markers, trusted_tools_used = True."""
        state = AgentState(query="quanto costa?", max_steps=1, current_step=0)
        state.final_answer = "Costa Rp 5.000.000 per il servizio"
        state.skip_rag = False

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: Costa Rp 5.000.000",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ITALIAN"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="how much?",
                system_prompt="sys",
                query="quanto costa?",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            assert result_state.trusted_tools_used is True

    @pytest.mark.asyncio
    async def test_llm_with_tools_available_trusts_output(self, engine):
        """If LLM had _gemini_tools and produced answer, trusted_tools_used = True."""
        state = AgentState(query="hello", max_steps=1, current_step=0)
        state.final_answer = "Hello! How can I help?"
        state.skip_rag = False

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = [MagicMock()]  # Has tools available
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: Hello!",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="hello",
                system_prompt="sys",
                query="hello",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            assert result_state.trusted_tools_used is True

    @pytest.mark.asyncio
    async def test_skip_rag_bypasses_evidence_check(self, engine):
        """skip_rag=True → evidence check skipped even with low score."""
        state = AgentState(query="translate this", max_steps=1, current_step=0, skip_rag=True)
        state.final_answer = "Here is the translation"

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: Here is the translation",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.01), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="translate",
                system_prompt="sys",
                query="translate this",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            # Answer should NOT be overridden
            assert result_state.final_answer == "Here is the translation"


# ============================================================================
# ReAct loop: tool parsing and execution
# ============================================================================

class TestReactLoop:

    @pytest.mark.asyncio
    async def test_no_tool_call_final_answer(self, engine):
        """When LLM returns 'Final Answer:' text, loop ends and answer is stored."""
        state = AgentState(query="hello", max_steps=3, current_step=0)
        from backend.services.llm_clients.pricing import TokenUsage

        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        mock_gateway.send_message = AsyncMock(return_value=(
            "Final Answer: Hi there!",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.5), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, model, msgs, usage = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="hello",
                system_prompt="sys",
                query="hello",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            assert result_state.final_answer == "Hi there!"
            assert len(result_state.steps) == 1
            assert result_state.steps[0].is_final is True

    @pytest.mark.asyncio
    async def test_llm_error_breaks_loop(self, engine):
        """When LLM raises ResourceExhausted, loop breaks gracefully."""
        from google.api_core.exceptions import ResourceExhausted
        from backend.services.llm_clients.pricing import TokenUsage

        state = AgentState(query="test", max_steps=3, current_step=0)
        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        mock_gateway.send_message = AsyncMock(side_effect=ResourceExhausted("quota"))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.0), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="test",
                system_prompt="sys",
                query="test",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            # Loop should have broken; no steps recorded since error was first step
            assert result_state.current_step == 1

    @pytest.mark.asyncio
    async def test_max_steps_reached(self, engine):
        """Loop ends when max_steps is reached."""
        from backend.services.llm_clients.pricing import TokenUsage

        state = AgentState(query="test", max_steps=1, current_step=0)
        mock_gateway = MagicMock()
        mock_gateway._gemini_tools = []
        mock_gateway.send_message = AsyncMock(return_value=(
            "Just thinking...",
            "gemini-flash",
            MagicMock(candidates=[]),
            TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.0), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):

            result_state, _, _, _ = await engine.execute_react_loop(
                state=state,
                llm_gateway=mock_gateway,
                chat=MagicMock(),
                initial_prompt="test",
                system_prompt="sys",
                query="test",
                user_id="u1",
                model_tier=1,
                tool_execution_counter={"count": 0},
            )
            assert result_state.current_step == 1
            assert result_state.final_answer == "Just thinking..."


# ============================================================================
# _TRUSTED_TOOL_NAMES constant
# ============================================================================

class TestTrustedToolNames:

    def test_trusted_tool_names_contains_expected(self):
        from backend.services.rag.agentic.reasoning import _TRUSTED_TOOL_NAMES
        assert "calculator" in _TRUSTED_TOOL_NAMES
        assert "get_pricing" in _TRUSTED_TOOL_NAMES
        assert "vector_search" in _TRUSTED_TOOL_NAMES
        assert "team_knowledge" in _TRUSTED_TOOL_NAMES
        assert "timesheet" in _TRUSTED_TOOL_NAMES

    def test_trusted_tool_names_is_frozenset(self):
        from backend.services.rag.agentic.reasoning import _TRUSTED_TOOL_NAMES
        assert isinstance(_TRUSTED_TOOL_NAMES, frozenset)
