"""Multi-agent grounding injection (2026-07-18).

Fix: requires_multi_agent()-routed queries (cost+timeline, multi-domain,
>5 entities) called coordinator.process() with only the extracted entities —
the orchestrator's system_context_for_prompt (curated_qa blocks + KG context
+ workflow) was dropped, so multi-agent answers were built ungrounded.

Consumers: LegalAgent.analyze() and MultiAgentCoordinator._synthesize_outputs()
get a HIGH PRIORITY evidence block appended to their prompt when
grounding_context is non-empty. FinancialAgent stays PricingService-SSOT
(deliberately untouched — mixing extra context would weaken its "use ONLY
the official prices above" instruction). TimelineAgent inherits grounded
facts transitively via legal_analysis (also untouched).

Guilt + innocence per consumer (scar family #3 discipline), plus one
orchestrator wiring test proving the injected curated block reaches
coordinator.process(grounding_context=...).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.multi_agent_coordinator import (
    FinancialAgent,
    LegalAgent,
    MultiAgentCoordinator,
    MultiAgentState,
)

VETTED_FACT = "[CURATED ref 2026-07-18]\nVetted fact."


def _base_state(**overrides) -> MultiAgentState:
    state: MultiAgentState = {
        "query": "How much will PT PMA cost and when can I start?",
        "user_context": {},
        "grounding_context": "",
        "legal_analysis": "",
        "financial_breakdown": "",
        "timeline_estimate": "",
        "agent_outputs": [],
        "final_answer": "",
        "errors": [],
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ── LegalAgent — guilt + innocence ──────────────────────────────────────────


class TestLegalAgentGrounding:
    @pytest.mark.asyncio
    async def test_grounding_present_is_injected_as_high_priority(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Legal analysis"))

        agent = LegalAgent(llm=mock_llm, kg_retrieval=None)
        state = _base_state(grounding_context=VETTED_FACT)

        result = await agent.analyze(state)

        prompt_sent = mock_llm.ainvoke.call_args[0][0]
        assert VETTED_FACT in prompt_sent
        assert "HIGH PRIORITY" in prompt_sent
        assert result["agent_outputs"][0]["had_grounding"] is True

    @pytest.mark.asyncio
    async def test_no_grounding_omits_header_and_marks_false(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Legal analysis"))

        agent = LegalAgent(llm=mock_llm, kg_retrieval=None)
        state = _base_state(grounding_context="")

        result = await agent.analyze(state)

        prompt_sent = mock_llm.ainvoke.call_args[0][0]
        assert "Pre-vetted evidence" not in prompt_sent
        assert result["agent_outputs"][0]["had_grounding"] is False


# ── Synthesizer — guilt + innocence ─────────────────────────────────────────


class TestSynthesizerGrounding:
    @pytest.mark.asyncio
    async def test_grounding_present_is_injected_as_high_priority(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Synthesized answer"))

        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            coordinator._llm = mock_llm

            state = _base_state(
                grounding_context=VETTED_FACT,
                legal_analysis="Legal stuff",
                financial_breakdown="Cost stuff",
                timeline_estimate="Timeline stuff",
            )

            await coordinator._synthesize_outputs(state)

        prompt_sent = mock_llm.ainvoke.call_args[0][0]
        assert VETTED_FACT in prompt_sent
        assert "HIGH PRIORITY" in prompt_sent

    @pytest.mark.asyncio
    async def test_no_grounding_omits_header(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Synthesized answer"))

        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            coordinator._llm = mock_llm

            state = _base_state(
                grounding_context="",
                legal_analysis="Legal stuff",
                financial_breakdown="Cost stuff",
                timeline_estimate="Timeline stuff",
            )

            await coordinator._synthesize_outputs(state)

        prompt_sent = mock_llm.ainvoke.call_args[0][0]
        assert "Pre-vetted evidence" not in prompt_sent


# ── FinancialAgent — innocence (SSOT-pure, never touched) ──────────────────


class TestFinancialAgentStaysUngrounded:
    @pytest.mark.asyncio
    async def test_grounding_context_never_reaches_financial_prompt(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Cost breakdown"))

        mock_pricing = MagicMock()
        mock_pricing.get_pricing = MagicMock(return_value={})
        mock_pricing.format_for_llm_context = MagicMock(return_value="Pricing data")
        mock_pricing.loaded = True

        agent = FinancialAgent(llm=mock_llm, pricing_service=mock_pricing)
        state = _base_state(grounding_context=VETTED_FACT)

        await agent.analyze(state)

        prompt_sent = mock_llm.ainvoke.call_args[0][0]
        assert "Pre-vetted evidence" not in prompt_sent
        assert VETTED_FACT not in prompt_sent


# ── process() kwarg wiring ──────────────────────────────────────────────────


class TestProcessGroundingKwarg:
    @pytest.mark.asyncio
    async def test_process_threads_grounding_context_into_initial_state(self):
        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            captured_state: dict = {}

            async def _fake_ainvoke(state: MultiAgentState) -> MultiAgentState:
                captured_state.update(state)
                return {**state, "final_answer": "done"}

            with patch.object(coordinator, "_ensure_initialized"):
                coordinator._graph = MagicMock()
                coordinator._graph.ainvoke = AsyncMock(side_effect=_fake_ainvoke)

                await coordinator.process(
                    query="test query",
                    grounding_context=VETTED_FACT,
                )

        assert captured_state["grounding_context"] == VETTED_FACT

    @pytest.mark.asyncio
    async def test_process_defaults_grounding_context_to_empty_string(self):
        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            captured_state: dict = {}

            async def _fake_ainvoke(state: MultiAgentState) -> MultiAgentState:
                captured_state.update(state)
                return {**state, "final_answer": "done"}

            with patch.object(coordinator, "_ensure_initialized"):
                coordinator._graph = MagicMock()
                coordinator._graph.ainvoke = AsyncMock(side_effect=_fake_ainvoke)

                await coordinator.process(query="test query")

        assert captured_state["grounding_context"] == ""
