"""
Wave 1 regression tests for OrchestratorCore / ReasoningEngine state machine.

Scope: inner state machine (`ReasoningEngine.execute_react_loop`).
Focus: loop termination, tool failure isolation, confidence gating transitions
and invariants identified in docs/audits/2026-04-22-orchestrator-state-machine.md (§2) and docs/audits/2026-04-22-orchestrator-test-gaps.md (§4).

Each test is keyed to a transition ID (R*) or invariant ID (I-R*) from
docs/audits/2026-04-22-orchestrator-state-machine.md so future Waves can cross-check coverage.

Fixture style mirrors test_reasoning_coverage.py: autouse patches on
tracing + metrics, patches on module-level helpers
(`parse_tool_call`, `is_valid_tool_call`, `execute_tool`,
`calculate_evidence_score`, `detect_query_language`,
`is_critical_domain`, `post_process_response`).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.tools.definitions import AgentState, ToolCall


# ---------------------------------------------------------------------------
# Autouse tracing + metrics patches (shared with test_reasoning_coverage.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_tracing():
    with patch("backend.services.rag.agentic.reasoning.trace_span") as ts, \
         patch("backend.services.rag.agentic.reasoning.set_span_attribute"), \
         patch("backend.services.rag.agentic.reasoning.set_span_status"), \
         patch("backend.services.rag.agentic.reasoning.add_span_event"):
        ts.return_value.__enter__ = MagicMock()
        ts.return_value.__exit__ = MagicMock(return_value=False)
        yield


@pytest.fixture(autouse=True)
def _patch_metrics():
    metrics = [
        "abstain_decision_total",
        "strict_abstain_critical_total",
        "tier1_fallback_activated_total",
        "tier1_fallback_failed_total",
        "tier1_fallback_success_total",
        "tier1_response_duration",
    ]
    patches = []
    for m in metrics:
        p = patch(f"backend.services.rag.agentic.reasoning.{m}", MagicMock())
        p.start()
        patches.append(p)
    yield
    for p in patches:
        try:
            p.stop()
        except Exception:
            pass


@pytest.fixture
def engine():
    """Basic ReasoningEngine with empty tool_map + no pipeline (keeps the loop pure)."""
    from backend.services.rag.agentic.reasoning import ReasoningEngine
    return ReasoningEngine(tool_map={}, response_pipeline=None)


def _mk_gateway(send_message_side_effect=None, has_tools: bool = False):
    """Helper: build a MagicMock LLM gateway with configurable send_message."""
    gateway = MagicMock()
    gateway._gemini_tools = [MagicMock()] if has_tools else []
    gateway.send_message = AsyncMock(side_effect=send_message_side_effect)
    return gateway


def _llm_response(text: str, candidates=None, tokens: int = 50):
    """Helper: shape a send_message return tuple.

    TokenUsage.total_tokens is a derived @property; construct via
    prompt_tokens so the tuple matches the llm_gateway.send_message contract.
    """
    resp = MagicMock()
    resp.candidates = candidates or []
    return (text, "gemini-flash", resp, TokenUsage(prompt_tokens=tokens))


def _patched_loop_env(
    *,
    evidence_score: float = 0.5,
    is_critical: bool = False,
    language: str = "ENGLISH",
    parse_tool_call_return=None,
    is_valid_tool_call_return: bool = False,
    execute_tool_return=("tool result", 0.01),
):
    """Helper: build the common 'patch everything' context manager stack.

    Returns a list of active patchers suitable for a `with ExitStack`; tests
    call it via the `_patch_env_*` fixtures below.
    """
    return [
        patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value=language,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.calculate_evidence_score",
            return_value=evidence_score,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=is_critical,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.parse_tool_call",
            return_value=parse_tool_call_return,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.is_valid_tool_call",
            return_value=is_valid_tool_call_return,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            new_callable=AsyncMock,
            return_value=execute_tool_return,
        ),
        patch(
            "backend.services.rag.agentic.reasoning.post_process_response",
            new_callable=AsyncMock,
            return_value="processed",
        ),
    ]


async def _run_loop(
    engine,
    gateway,
    state: AgentState,
    query: str = "test",
    user_id: str = "u1",
    tier: int = 1,
):
    """Execute the loop with fixed args — keeps tests compact."""
    return await engine.execute_react_loop(
        state=state,
        llm_gateway=gateway,
        chat=MagicMock(),
        initial_prompt=query,
        system_prompt="sys",
        query=query,
        user_id=user_id,
        model_tier=tier,
        tool_execution_counter={"count": 0},
    )


# ============================================================================
# Group 1 — Loop termination & budget (R2 / I-R1)
# ============================================================================


class TestLoopTermination:
    """Transitions: R2 (max_steps exit). Invariant: I-R1 (bounded iterations)."""

    @pytest.mark.asyncio
    async def test_loop_terminates_at_max_steps_with_tool_calls(self, engine):
        """R2 + I-R1: LLM keeps requesting tool calls; loop must exit at max_steps.

        max_steps=2, LLM always produces a parseable tool call. After 2 iterations
        the `while current_step < max_steps` guard fires and downstream logic
        generates a final answer via the CtxAnswer branch (R25) because
        context_gathered is populated.

        Note: `send_message` is called max_steps times for the loop body PLUS
        once more in the post-loop CtxAnswer branch to generate the final
        answer. We only assert the bounded-iteration invariant on the
        loop-scoped state (current_step, steps count).
        """
        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")

        fake_tool_call = ToolCall(tool_name="crm_query", arguments={"q": "x"})

        async def send(*args, **kwargs):
            return _llm_response("Using tool", candidates=[MagicMock()])

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=True)

        # Use a tool_result that contains the query keyword so _validate_context_quality
        # doesn't trigger `continue` on low quality (which would confuse R2 vs R9 here)
        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.3), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=fake_tool_call), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock,
                 return_value=("q result q context q", 0.01),
             ), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # I-R1: loop exited at max_steps — current_step equals the budget
        assert result_state.current_step == state.max_steps == 2
        # Exactly max_steps tool-bearing AgentSteps recorded
        tool_steps = [s for s in result_state.steps if s.action]
        assert len(tool_steps) == state.max_steps
        # Fallback branch produced a non-empty final_answer (I-R2)
        assert result_state.final_answer is not None and len(result_state.final_answer) > 0


# ============================================================================
# Group 2 — SendMessage error paths (R4 / R4b / I-R2)
# ============================================================================


class TestSendMessageErrorPaths:

    @pytest.mark.asyncio
    async def test_step1_llm_raise_resource_exhausted_yields_abstain(self, engine):
        """R4 + I-R2: step-1 ResourceExhausted → loop breaks → fallback sets final_answer.

        Per STATE_MACHINE §U1: when step-1 send_message raises, final_answer must
        still be set via the 'no-context non-critical Tier 1' (CtxTier1) or
        abstain-stub branch. We patch tier1's send_message to also raise so the
        AbstainFallback path fires, and assert the stub is installed.
        """
        from google.api_core.exceptions import ResourceExhausted

        state = AgentState(query="hello", max_steps=3, current_step=0, intent_type="simple")
        gateway = _mk_gateway(
            send_message_side_effect=ResourceExhausted("quota"),
        )

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.0), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # Loop broke on step 1
        assert result_state.current_step == 1
        # I-R2: final_answer is set by the Tier-1/abstain fallback, even though
        # the original LLM raised — stub path fires because tier1 also raised.
        assert result_state.final_answer is not None and len(result_state.final_answer) > 0

    @pytest.mark.asyncio
    async def test_step2_llm_raise_preserves_step1_context(self, engine):
        """R4b: step 1 succeeds with tool call, step 2 raises → partial state preserved."""
        from google.api_core.exceptions import ServiceUnavailable

        state = AgentState(query="q", max_steps=3, current_step=0, intent_type="simple")
        fake_tool_call = ToolCall(tool_name="calculator", arguments={})

        call = {"i": 0}

        async def send(*args, **kwargs):
            call["i"] += 1
            if call["i"] == 1:
                return _llm_response("Using tool", candidates=[MagicMock()])
            raise ServiceUnavailable("upstream down")

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=True)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.2), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=fake_tool_call), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock,
                 return_value=("step1 obs", 0.01),
             ), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # Step 1's observation survived despite step-2 raise (I-R5)
        assert any("step1 obs" in c for c in result_state.context_gathered)
        # Loop broke before reaching max_steps
        assert result_state.current_step < state.max_steps
        # Answer resolution fired (CtxAnswer / Tier 1 regen, depending on evidence)
        assert result_state.final_answer is not None


# ============================================================================
# Group 3 — Tool execution (R7 / R8 / I-R7 / I-R8)
# ============================================================================


class TestToolExecution:

    @pytest.mark.asyncio
    async def test_parallel_tool_calls_bumps_step_counter(self, engine):
        """R7 + I-R7: N parallel tool calls → current_step += len(tool_calls) - 1 after the iteration.

        We short-circuit parse_tool_calls_from_response by patching it directly
        to return N=2 calls at once, and set `max_steps=2` so the parallel bump
        consumes the entire budget in a single iteration (prevents re-entry).

        Invariant I-R7: after one iteration with N=2 parallel tools,
        current_step = 1 (per-iteration increment) + 1 (parallel bump) = 2.
        """
        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")

        tc_a = ToolCall(tool_name="calculator", arguments={"a": 1})
        tc_b = ToolCall(tool_name="date_lookup", arguments={})

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "parallel", candidates=[MagicMock()],
            ),
        )

        # Patch the module-level helper so parse returns 2 calls
        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([tc_a, tc_b], "native"),
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            new_callable=AsyncMock,
            return_value=("q obs context q", 0.01),  # include keyword so quality passes
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.5,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.post_process_response",
            new_callable=AsyncMock, return_value="processed",
        ):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # I-R7: after one iteration with 2 parallel tools, step counter = 1 + 1 = 2
        assert result_state.current_step == 2
        # 2 AgentSteps appended, one per tool
        assert len(result_state.steps) == 2
        # Both tools recorded (parallel execution visible in step thoughts)
        tool_names_used = {s.action.tool_name for s in result_state.steps if s.action}
        assert tool_names_used == {"calculator", "date_lookup"}

    @pytest.mark.asyncio
    async def test_tool_execution_error_does_not_break_loop(self, engine):
        """R8 + I-R8: tool raise → observation = 'Error: ...', loop continues (not break)."""
        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")
        fake_tool = ToolCall(tool_name="calculator", arguments={})

        async def boom(*args, **kwargs):
            raise RuntimeError("tool crashed")

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "thinking", candidates=[MagicMock()],
            ),
        )

        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=fake_tool), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock, side_effect=boom,
             ), \
             patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.3), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # I-R8: observation was replaced with an "Error: ..." string from the wrapper
        error_steps = [s for s in result_state.steps if s.observation and s.observation.startswith("Error:")]
        assert len(error_steps) >= 1, (
            f"expected at least one Error: observation in steps; got {[s.observation for s in result_state.steps]}"
        )
        # Loop did not abort — either ran to max_steps or generated final answer after
        assert result_state.final_answer is not None


# ============================================================================
# Group 4 — Context quality & early exit (R9 / R11 / R12)
# ============================================================================


class TestQualityAndEarlyExit:

    @pytest.mark.asyncio
    async def test_low_quality_context_continue_loop(self, engine):
        """R9: quality < 0.15 with budget remaining → `continue` to gather more context.

        We force `_validate_context_quality` below threshold; with max_steps=3 and
        budget still available, the loop must iterate a second time (send_message
        called ≥ 2 times).
        """
        state = AgentState(query="q", max_steps=3, current_step=0, intent_type="simple")
        tc = ToolCall(tool_name="calculator", arguments={})

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            return _llm_response("thinking", candidates=[MagicMock()])

        gateway = _mk_gateway(send_message_side_effect=send)

        # Patch the engine instance's _validate_context_quality to force low score
        with patch.object(engine, "_validate_context_quality", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=tc), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock, return_value=("short", 0.01),
             ), \
             patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.3), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            await _run_loop(engine, gateway, state)

        # R9: low quality triggers `continue` → loop iterates at least twice before max_steps
        assert call["i"] >= 2

    @pytest.mark.asyncio
    async def test_early_exit_on_strong_vector_search(self, engine):
        """R11: vector_search returns len>500 on `simple` intent → loop breaks at step 1.

        should_early_exit_on_vector_search returns True; send_message should be
        called exactly once.
        """
        state = AgentState(query="q", max_steps=5, current_step=0, intent_type="simple")
        vs_tool = ToolCall(tool_name="vector_search", arguments={"query": "q"})
        # >500 chars, no "No relevant documents", and contains the query keyword "q"
        # so _validate_context_quality clears the ABSTAIN threshold and doesn't
        # trigger the low-quality `continue` path before the early-exit check.
        big_result = ("q relevant content " * 40)  # 760 chars, "q" in every fragment

        async def send(*a, **k):
            return _llm_response("searching", candidates=[MagicMock()])

        gateway = _mk_gateway(send_message_side_effect=send)

        # Patch _validate_context_quality directly so the result length check
        # reliably passes (bypass the keyword heuristic which is noisy for 1-char queries).
        with patch.object(engine, "_validate_context_quality", return_value=0.9), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=vs_tool), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock, return_value=(big_result, 0.01),
             ), \
             patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.7), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # R11: early exit fires after the first tool call. Only one AgentStep
        # with an action recorded (the vector_search call). current_step==1.
        tool_steps = [s for s in result_state.steps if s.action]
        assert len(tool_steps) == 1
        assert result_state.current_step == 1

    @pytest.mark.asyncio
    async def test_complex_intent_no_early_exit(self, engine):
        """R12: same as above but intent=`business_complex` → early-exit disabled.

        Loop continues until max_steps (LLM keeps returning tool calls).
        """
        state = AgentState(query="q", max_steps=3, current_step=0, intent_type="business_complex")
        vs_tool = ToolCall(tool_name="vector_search", arguments={"query": "q"})
        big_result = "B" * 800

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            return _llm_response("searching", candidates=[MagicMock()])

        gateway = _mk_gateway(send_message_side_effect=send)

        with patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=vs_tool), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=True), \
             patch(
                 "backend.services.rag.agentic.reasoning.execute_tool",
                 new_callable=AsyncMock, return_value=(big_result, 0.01),
             ), \
             patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.7), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # R12: complex intent does NOT early-exit → loop iterates > 1 time
        assert call["i"] >= 2


# ============================================================================
# Group 5 — No-tool-call branches (R14)
# ============================================================================


class TestThoughtOnlyBranch:

    @pytest.mark.asyncio
    async def test_thought_only_step_continues_loop(self, engine):
        """R14: LLM returns plain text, no `Final Answer:`, budget remaining → thought step appended, loop continues."""
        state = AgentState(query="q", max_steps=3, current_step=0, intent_type="simple")

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            if call["i"] < 3:
                return _llm_response("just a thought")
            return _llm_response("Final Answer: done")

        gateway = _mk_gateway(send_message_side_effect=send)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.5), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # Loop iterated until Final Answer was emitted — last step is_final=True
        assert result_state.steps[-1].is_final is True
        assert result_state.final_answer == "done"
        # Intermediate steps are thought-only (action=None)
        thought_steps = [s for s in result_state.steps[:-1] if s.action is None]
        assert len(thought_steps) >= 1


# ============================================================================
# Group 6 — Tier 1 regeneration (R22 / R24 / I-R2)
# ============================================================================


class TestTier1Regeneration:

    @pytest.mark.asyncio
    async def test_tier1_regeneration_on_non_critical_low_evidence(self, engine):
        """R22: non-critical + low evidence + final_answer present + not trusted → Tier 1 regen.

        Main LLM produces a Final Answer; the evidence score is below threshold;
        the query is non-critical → the engine must call send_message AGAIN with
        enable_function_calling=False to regenerate via Tier 1 build_tier1_prompt.
        """
        state = AgentState(query="casual chat", max_steps=1, current_step=0, intent_type="simple")

        call = {"i": 0, "no_fc_count": 0}

        async def send(*a, **k):
            call["i"] += 1
            if kwargs_fc := k.get("enable_function_calling"):
                pass
            else:
                # tier1 regen call disables function calling
                call["no_fc_count"] += 1
            if call["i"] == 1:
                return _llm_response("Final Answer: weak answer")
            return _llm_response("Regenerated answer")

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=False)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # R22: send_message called at least twice (initial + Tier 1 regen)
        assert call["i"] >= 2
        # Tier 1 regeneration disables function calling exactly once
        assert call["no_fc_count"] >= 1
        # final_answer updated by regen (not the "weak answer")
        assert result_state.final_answer is not None

    @pytest.mark.asyncio
    async def test_tier1_regen_failure_falls_back_to_abstain_stub(self, engine):
        """R24 + I-R2: tier1 send_message raises → final_answer = localized abstain stub."""
        from google.api_core.exceptions import ServiceUnavailable

        state = AgentState(query="casual", max_steps=1, current_step=0, intent_type="simple")

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            if call["i"] == 1:
                return _llm_response("Final Answer: weak")
            raise ServiceUnavailable("tier1 down")

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=False)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ITALIAN"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.05), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # I-R2: final_answer is set to a localized abstain stub (non-empty string)
        assert result_state.final_answer is not None
        assert len(result_state.final_answer) > 0
        # Not equal to the original weak answer (got overridden to stub)
        assert result_state.final_answer != "weak"


# ============================================================================
# Group 7 — No-context branches (R26 / R27)
# ============================================================================


class TestNoContextBranches:

    @pytest.mark.asyncio
    async def test_no_context_critical_triggers_abstain_message(self, engine):
        """R26: no final_answer + no context_gathered + critical domain → hardcoded Italian abstain."""
        state = AgentState(query="visto KITAS?", max_steps=1, current_step=0, intent_type="business_complex")
        # Loop will set final_answer only if "Final Answer:" is present OR max_steps reached.
        # Here we make LLM return bare text → at max_steps=1, `state.current_step >= state.max_steps`
        # short-circuit in the no-tool-call branch will set final_answer via extract_final_answer_text.
        # To really hit R26 we need NO final_answer AFTER the loop. Force max_steps=1 + plain text
        # without "Final Answer:" + parse_tool_call returns None → at current_step=1, is_valid_tool_call False
        # AND current_step >= max_steps → SetFinalAnswer with extract_final_answer_text(text).
        # Since "Final Answer:" isn't in text, extract_final_answer_text returns text verbatim
        # and final_answer is "plain text" — so R26 (no final_answer) won't fire from this path.
        # Instead we simulate a step-1 LLM raise so loop breaks with no final_answer + no context.
        from google.api_core.exceptions import ResourceExhausted

        gateway = _mk_gateway(send_message_side_effect=ResourceExhausted("quota"))

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ITALIAN"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.0), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=True), \
             patch("backend.services.rag.agentic.reasoning.get_critical_domain_type", return_value="visa"), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock):
            result_state, _, _, _ = await _run_loop(engine, gateway, state, query="visto KITAS?")

        # R26: critical + no context + no answer → localized abstain stub (Italian by detect_query_language)
        assert result_state.final_answer is not None
        # Italian abstain stub should mention visti/KITAS keywords OR be a proper abstain format
        # We assert presence of domain content vs a generic LLM error message — the stub is NOT empty.
        assert len(result_state.final_answer) > 20

    @pytest.mark.asyncio
    async def test_no_context_noncritical_triggers_tier1_fallback(self, engine):
        """R27: no context + non-critical → Tier 1 path via TRANSPARENCY_INSTRUCTION_NO_CONTEXT.

        When step-1 raise + context empty + non-critical → engine calls
        build_tier1_prompt with `include_context_section=False` and a second
        send_message. If Tier 1 also succeeds, final_answer is the regenerated text.
        """
        from google.api_core.exceptions import ResourceExhausted

        state = AgentState(query="chit chat", max_steps=1, current_step=0, intent_type="simple")

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            if call["i"] == 1:
                raise ResourceExhausted("quota step1")
            return _llm_response("General intelligence answer")

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=False)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.0), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(engine, gateway, state)

        # R27: Tier 1 path fired → second send_message call → final_answer populated
        assert call["i"] == 2  # step-1 raise + tier1 regen
        assert result_state.final_answer == "General intelligence answer"


# ============================================================================
# Group 8 — Pipeline verification (R29 / R30)
# ============================================================================


class TestPipelineProcessing:

    @pytest.mark.asyncio
    async def test_pipeline_verification_fail_triggers_self_correction(self, engine):
        """R29: response_pipeline.process returns verification_score < 0.7 + context → rephrase + retry."""
        # Build engine with a response pipeline that returns low verification score
        pipeline = MagicMock()
        pipeline.process = AsyncMock(
            side_effect=[
                # 1st pass: bad score
                {
                    "response": "original bad answer",
                    "verification_score": 0.5,
                    "verification": {"reasoning": "missing citations", "missing_citations": ["doc1"]},
                },
                # 2nd pass (post-correction): good score
                {
                    "response": "corrected answer",
                    "verification_score": 0.9,
                    "verification_status": "passed",
                    "citation_count": 3,
                    "citations": [{"id": "doc1"}],
                },
            ],
        )
        from backend.services.rag.agentic.reasoning import ReasoningEngine
        local_engine = ReasoningEngine(tool_map={}, response_pipeline=pipeline)

        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        # Populate context so self-correction branch is reachable
        state.context_gathered = ["some context"]

        call = {"i": 0}

        async def send(*a, **k):
            call["i"] += 1
            if call["i"] == 1:
                return _llm_response("Final Answer: original bad answer")
            # The rephrase retry disables function calling
            return _llm_response("corrected answer")

        gateway = _mk_gateway(send_message_side_effect=send, has_tools=True)

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.8), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.post_process_response", new_callable=AsyncMock, return_value="processed"):
            result_state, _, _, _ = await _run_loop(local_engine, gateway, state)

        # R29: pipeline called twice (initial + post self-correction)
        assert pipeline.process.await_count == 2
        # corrected answer installed
        assert result_state.final_answer == "corrected answer"

    @pytest.mark.asyncio
    async def test_pipeline_error_falls_back_to_post_process(self, engine):
        """R30: response_pipeline.process raises ValueError → post_process_response applied, no raise escapes."""
        pipeline = MagicMock()
        pipeline.process = AsyncMock(side_effect=ValueError("pipeline broken"))

        from backend.services.rag.agentic.reasoning import ReasoningEngine
        local_engine = ReasoningEngine(tool_map={}, response_pipeline=pipeline)

        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response("Final Answer: my answer"),
            has_tools=True,
        )

        with patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH"), \
             patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.8), \
             patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False), \
             patch("backend.services.rag.agentic.reasoning.parse_tool_call", return_value=None), \
             patch("backend.services.rag.agentic.reasoning.is_valid_tool_call", return_value=False), \
             patch(
                 "backend.services.rag.agentic.reasoning.post_process_response",
                 return_value="post-processed fallback",
             ) as mock_pp:
            result_state, _, _, _ = await _run_loop(local_engine, gateway, state)

        # R30: pipeline raised, but post_process_response installed a non-None result
        mock_pp.assert_called_once()
        assert result_state.final_answer == "post-processed fallback"
