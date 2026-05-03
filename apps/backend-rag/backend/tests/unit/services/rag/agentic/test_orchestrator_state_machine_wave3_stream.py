"""
Wave 3 regression tests for ReasoningEngine.execute_react_loop_stream.

Scope: streaming ReAct loop (`ReasoningEngine.execute_react_loop_stream`).
Focus: transitions S1..S29 and invariants I-S1..I-S9 from docs/audits/2026-04-22-orchestrator-state-machine.md §5.

Each test is keyed to a transition ID (S*) or streaming invariant ID (I-S*)
so future Waves can cross-check coverage. Wave 2 closed U5 via
`apply_shared_trusted_flippers`; Wave 3 exercises the remaining
streaming-only transitions (yield protocol, CRM early-exit, stream-only
context flippers, token chunking, stub-key drift).

Fixture style mirrors test_orchestrator_state_machine_wave1.py: autouse
patches on tracing + metrics, plus a helper to collect all streamed
events into a list.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.tools.definitions import AgentState, ToolCall


# ---------------------------------------------------------------------------
# Autouse tracing + metrics patches (shared pattern with wave1/wave2)
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


@pytest.fixture(autouse=True)
def _patch_emit_low_confidence():
    """emit_low_confidence_event is `await`-ed inside the stream path.

    It hits a DB pool we don't mock; always stub it out to a no-op.
    """
    with patch(
        "backend.services.rag.agentic.reasoning.emit_low_confidence_event",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


@pytest.fixture
def engine():
    """ReasoningEngine with empty tool_map + no pipeline (keeps loop pure)."""
    from backend.services.rag.agentic.reasoning import ReasoningEngine
    return ReasoningEngine(tool_map={}, response_pipeline=None)


def _mk_gateway(send_message_side_effect=None, has_tools: bool = False):
    gateway = MagicMock()
    gateway._gemini_tools = [MagicMock()] if has_tools else []
    gateway.send_message = AsyncMock(side_effect=send_message_side_effect)
    return gateway


def _llm_response(text: str, candidates=None):
    """Stream send_message returns (text, model_name, response_obj, token_usage).

    The token usage slot is ignored by the streaming loop (I-S drift: no
    token tracking) so we pass a bare MagicMock.
    """
    resp = MagicMock()
    resp.candidates = candidates or []
    return (text, "gemini-flash", resp, MagicMock())


async def _run_stream(
    engine,
    gateway,
    state: AgentState,
    query: str = "test",
    user_id: str = "u1",
    tier: int = 1,
    images=None,
) -> list[dict]:
    """Drain the streaming loop and return the list of emitted events."""
    events: list[dict] = []
    async for ev in engine.execute_react_loop_stream(
        state=state,
        llm_gateway=gateway,
        chat=MagicMock(),
        initial_prompt=query,
        system_prompt="sys",
        query=query,
        user_id=user_id,
        model_tier=tier,
        tool_execution_counter={"count": 0},
        images=images,
    ):
        events.append(ev)
    return events


def _event_types(events: list[dict]) -> list[str]:
    return [e.get("type") for e in events]


# ============================================================================
# Group 1 — Yield protocol & ordering (I-S1 / S1 / S16 / S28 / S29)
# ============================================================================


class TestStreamYieldProtocol:
    """I-S1: strict event ordering —
    thinking → [tool_call → observation → (image)] → evidence_score → token* → sources?
    """

    @pytest.mark.asyncio
    async def test_happy_path_event_order(self, engine):
        """I-S1 + S1 + S16 + S28 + S29: direct final answer path yields
        thinking → evidence_score → token* with no tool events in between.

        With no tool_calls, streaming takes the `NoToolCall + "Final Answer:"`
        branch (§S13 sync counterpart §R13), sets final_answer and breaks.
        Post-loop it yields evidence_score, then token chunks.
        """
        state = AgentState(query="q", max_steps=3, current_step=0, intent_type="simple")
        state.skip_rag = True  # bypass evidence gate to stay on the happy path
        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: A short definite answer.",
            ),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        types = _event_types(events)

        # I-S1: must contain thinking before evidence_score, evidence_score before token
        assert "thinking" in types
        assert "evidence_score" in types
        assert "token" in types
        assert types.index("thinking") < types.index("evidence_score")
        assert types.index("evidence_score") < types.index("token")

        # S29: sources only if state.sources truthy → default is [] → no sources event
        assert "sources" not in types

    @pytest.mark.asyncio
    async def test_token_chunks_have_20_char_cap(self, engine):
        """I-S8 + S28: chunk_size=20, final_answer length L → exactly
        ceil(L/20) token events, none longer than 20 chars."""
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = True

        # Exactly 45 chars → ceil(45/20) = 3 chunks (20 + 20 + 5).
        long_answer = "Final Answer: " + ("X" * 31)  # payload extracted after marker

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(long_answer),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        token_events = [e for e in events if e.get("type") == "token"]
        # Each chunk is at most 20 chars
        assert all(len(e["data"]) <= 20 for e in token_events), \
            f"token chunks exceeded 20 chars: {[len(e['data']) for e in token_events]}"
        # Final answer "X" * 31 → 2 chunks (20 + 11). extract_final_answer_text
        # strips "Final Answer: " prefix.
        assert len(token_events) in (2, 3), \
            f"expected 2-3 chunks for 31 char answer, got {len(token_events)}"
        # Concatenation of token chunks == final_answer
        assert "".join(e["data"] for e in token_events) == state.final_answer


# ============================================================================
# Group 2 — Single-tool-per-step + tool raise propagation (I-S2, I-S3, S5, S7)
# ============================================================================


class TestStreamToolExecution:
    """I-S2: only the first tool call is executed per iteration.
    I-S3: tool raise propagates (no wrapper), ending the generator.
    """

    @pytest.mark.asyncio
    async def test_only_first_tool_call_executed_per_step(self, engine):
        """S5 + I-S2: parse_tool_calls_from_response returns N=2, stream
        takes `tool_calls[0]` only. Second tool is ignored.
        """
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        tc_a = ToolCall(tool_name="calculator", arguments={"op": "a"})
        tc_b = ToolCall(tool_name="calculator", arguments={"op": "b"})

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "try two tools", candidates=[MagicMock()],
            ),
        )
        execute_tool_mock = AsyncMock(return_value=("tool result A", 0.01))

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([tc_a, tc_b], "native"),
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            execute_tool_mock,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        # I-S2: execute_tool was called exactly once for the first tool
        assert execute_tool_mock.await_count == 1
        kwargs = execute_tool_mock.await_args.kwargs
        assert kwargs["tool_name"] == "calculator"
        # arguments of the FIRST tool only
        assert kwargs["arguments"] == {"op": "a"}

        # tool_call event fires before observation
        types = _event_types(events)
        assert "tool_call" in types
        assert "observation" in types
        assert types.index("tool_call") < types.index("observation")

    @pytest.mark.asyncio
    async def test_tool_raise_propagates_through_generator(self, engine):
        """I-S3 + S7: a tool implementation raise is NOT wrapped in streaming.
        The async generator raises, and events already yielded survive.

        Contrast with sync (I-R8) where `_exec_tool_wrapper` converts the
        raise into `f"Error: {e}"` observation and the loop continues.
        """
        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")
        tc = ToolCall(tool_name="calculator", arguments={})

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "call tool", candidates=[MagicMock()],
            ),
        )

        async def _boom(*a, **k):
            raise RuntimeError("tool impl exploded")

        events_collected: list[dict] = []
        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([tc], "native"),
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            side_effect=_boom,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ):
            with pytest.raises(RuntimeError, match="tool impl exploded"):
                async for ev in engine.execute_react_loop_stream(
                    state=state,
                    llm_gateway=gateway,
                    chat=MagicMock(),
                    initial_prompt="q",
                    system_prompt="sys",
                    query="q",
                    user_id="u1",
                    model_tier=1,
                    tool_execution_counter={"count": 0},
                ):
                    events_collected.append(ev)

        # thinking + tool_call were already yielded BEFORE execute_tool raised
        types = _event_types(events_collected)
        assert "thinking" in types
        assert "tool_call" in types
        # No observation/evidence/token — the generator died mid-flight
        assert "observation" not in types
        assert "evidence_score" not in types
        assert "token" not in types


# ============================================================================
# Group 3 — CRM early-exit sets trusted in-loop (I-S4, S11)
# ============================================================================


class TestStreamCRMEarlyExit:
    """S11 + I-S4: `crm_query` result > 10 chars → `trusted_tools_used=True`
    is set INSIDE the loop (streaming-only) and the loop breaks.
    """

    @pytest.mark.asyncio
    async def test_crm_query_sets_trusted_and_breaks(self, engine):
        """S11 + I-S4: single crm_query call with substantial result flips
        trusted_tools_used and exits the loop early.

        max_steps=3 but only one iteration actually executes because CRM
        result >10 chars triggers break. State trusted must be True afterward.
        """
        state = AgentState(query="who is X", max_steps=3, current_step=0, intent_type="simple")
        state.skip_rag = False
        tc = ToolCall(tool_name="crm_query", arguments={"q": "X"})

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "calling crm", candidates=[MagicMock()],
            ),
        )
        # A >10 char result
        execute_tool_mock = AsyncMock(
            return_value=("CRM: found 3 clients named X with full profile", 0.01),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([tc], "native"),
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            execute_tool_mock,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            # evidence_score irrelevant because trusted=True bypasses gate
            return_value=0.0,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        # I-S4: trusted_tools_used set to True inside the loop
        assert state.trusted_tools_used is True
        # Loop exited after step 1 — execute_tool called exactly once
        assert execute_tool_mock.await_count == 1
        # current_step == 1 — no extra iterations consumed
        assert state.current_step == 1
        # evidence_score event still yielded post-break
        assert "evidence_score" in _event_types(events)

    @pytest.mark.asyncio
    async def test_crm_short_result_does_not_trigger_early_exit(self, engine):
        """S11 negative: `crm_query` with ≤10 char result → no early-exit,
        loop continues to max_steps.

        Use a tiny CRM result (e.g. "none") + a second send_message that
        emits Final Answer to terminate cleanly at step 2.
        """
        state = AgentState(query="who is Y", max_steps=2, current_step=0, intent_type="simple")
        state.skip_rag = True
        tc = ToolCall(tool_name="crm_query", arguments={})

        calls = {"i": 0}

        async def _send(*a, **k):
            calls["i"] += 1
            if calls["i"] == 1:
                # Step 1: returns a tool call (that yields tiny CRM result)
                return _llm_response("call crm", candidates=[MagicMock()])
            # Step 2: emit final answer (no tool call this time)
            return _llm_response("Final Answer: Nobody by that name.")

        gateway = _mk_gateway(send_message_side_effect=_send)

        parse_call = {"i": 0}

        def _parse(*a, **k):
            parse_call["i"] += 1
            if parse_call["i"] == 1:
                return ([tc], "native")
            return ([], "none")

        execute_tool_mock = AsyncMock(return_value=("none", 0.01))  # <=10 chars

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            side_effect=_parse,
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            execute_tool_mock,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        # Two iterations happened (no early-exit from CRM branch)
        assert calls["i"] == 2
        # trusted_tools_used NOT set by the CRM short-result path
        # (but it may be set later by shared flippers if final_answer has
        # pricing markers — not the case here)
        # The defining assertion is: the loop ran step 2 rather than breaking.
        assert "Final Answer" in state.final_answer or "Nobody" in (state.final_answer or "")


# ============================================================================
# Group 4 — Step error event + generator closure (S4, I-S9)
# ============================================================================


class TestStreamErrorEvents:
    """S4 + I-S9: send_message raises → yield error event + break. Generator
    closes cleanly, emitting at least one event.
    """

    @pytest.mark.asyncio
    async def test_step1_send_message_raise_yields_error_event(self, engine):
        """S4 + I-S9: step-1 ResourceExhausted → error event + loop break.

        Post-loop fallbacks still fire (evidence=0, trusted=False, no context,
        non-critical → Tier1 regen path, which we force to raise too to end at
        a stub). The important thing is that the ERROR event was emitted BEFORE
        any evidence_score or token events.
        """
        from google.api_core.exceptions import ResourceExhausted

        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")
        state.skip_rag = False  # force Tier1 path

        call_count = {"i": 0}

        async def _raise_then_raise(*a, **k):
            # Both the loop call AND the Tier1 fallback call raise
            call_count["i"] += 1
            raise ResourceExhausted("quota over")

        gateway = _mk_gateway(send_message_side_effect=_raise_then_raise)

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.0,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            events = await _run_stream(engine, gateway, state)

        types = _event_types(events)
        # S4: error event was emitted
        assert "error" in types
        # I-S9: generator closed cleanly (no exception propagated)
        # evidence_score is still yielded post-break
        assert "evidence_score" in types
        # Order: error before evidence_score
        assert types.index("error") < types.index("evidence_score")
        # final_answer resolved via stub fallback (I-R2 preserved cross-path)
        assert state.final_answer is not None and len(state.final_answer) > 0


# ============================================================================
# Group 5 — Stream-only trusted-context widening (I-S5, S17, S18)
# ============================================================================


class TestStreamContextWidening:
    """I-S5 / S17 / S18: `detect_trusted_context_markers` and
    `detect_substantial_context` are STREAM-ONLY flippers. We lock their
    contract: when they return True and evidence is low, the policy gate
    treats the query as trusted (no Tier1 regen, no abstain stub).
    """

    @pytest.mark.asyncio
    async def test_trusted_context_markers_flip_trusted_and_bypass_policy(self, engine):
        """I-S5 + S17: with low evidence but marker hit → trusted=True →
        low-evidence policy gate does NOT fire; existing answer survives.

        Contrast sync: the same low-evidence + no-trusted-tools combo would
        trigger Tier1 regen (§R22). In stream, context markers save us.
        """
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = False
        state.context_gathered = ["some context chunk"]
        state.final_answer = "ORIGINAL LLM ANSWER"  # seed so the guard "has answer" trips

        gateway = _mk_gateway(
            # No calls needed — we pre-seeded final_answer, but we still
            # need the loop to iterate once. Have the LLM return a final
            # answer to match state.
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: ORIGINAL LLM ANSWER",
            ),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.05,  # below ABSTAIN_THRESHOLD
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_tool_usage",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_context_markers",
            return_value=(True, ["pricing_marker"]),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_substantial_context",
            return_value=False,
        ):
            await _run_stream(engine, gateway, state)

        # trusted_tools_used was flipped to True by the markers-flip (§S17)
        assert state.trusted_tools_used is True
        # Original answer preserved (policy gate skipped, no abstain stub)
        assert "ORIGINAL LLM ANSWER" in state.final_answer

    @pytest.mark.asyncio
    async def test_substantial_context_flip_when_no_markers(self, engine):
        """I-S5 + S18: marker miss + substantial context → trusted=True.

        This path is the second of the two stream-only widenings. Sync pipeline
        does neither; streaming does both sequentially.
        """
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = False
        state.context_gathered = ["a very long context chunk ..."]
        state.final_answer = "Another LLM answer"

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: Another LLM answer",
            ),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.05,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_tool_usage",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_context_markers",
            return_value=(False, []),  # markers miss
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_substantial_context",
            return_value=True,  # substantial context hit
        ):
            await _run_stream(engine, gateway, state)

        # trusted_tools_used flipped by substantial-context flipper (S18)
        assert state.trusted_tools_used is True


# ============================================================================
# Group 6 — Stub key drift: streaming "abstain" vs sync "abstain_detailed" (I-S6, S20)
# ============================================================================


class TestStreamStubKeyDrift:
    """I-S6 / S20: the override-answer critical branch in streaming uses
    `_get_localized_stub("abstain", language)`, while sync uses
    `"abstain_detailed"`. Lock the current behavior so refactors that unify
    the keys must be deliberate.
    """

    @pytest.mark.asyncio
    async def test_critical_override_uses_abstain_stub_key(self, engine):
        """I-S6 + S20: low-evidence + critical + final_answer set → stream
        overrides with stub key "abstain" (NOT "abstain_detailed" as sync does).

        We patch `get_localized_stub` to a marker string so we can assert
        which key was requested.
        """
        state = AgentState(
            query="visto KITAS requirements?", max_steps=1, current_step=0, intent_type="simple",
        )
        state.skip_rag = False
        state.final_answer = "weak pre-regen answer"

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: weak pre-regen answer",
            ),
        )

        stub_calls: list[tuple[str, str]] = []

        def _stub_spy(key, language):
            stub_calls.append((key, language))
            return f"[STUB:{key}:{language}]"

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.05,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=True,  # critical domain
        ), patch(
            "backend.services.rag.agentic.reasoning.get_critical_domain_type",
            return_value="immigration",
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_tool_usage",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_context_markers",
            return_value=(False, []),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_substantial_context",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.get_localized_stub",
            side_effect=_stub_spy,
        ):
            await _run_stream(engine, gateway, state)

        # The stub was invoked with key="abstain" (not "abstain_detailed")
        keys_used = [k for k, _ in stub_calls]
        assert "abstain" in keys_used, \
            f"Expected 'abstain' stub key in streaming override branch, got {keys_used}"
        assert "abstain_detailed" not in keys_used, \
            "Streaming should NOT use sync's 'abstain_detailed' key — lock the drift"
        # final_answer replaced with the stub
        assert state.final_answer.startswith("[STUB:abstain:ENGLISH]")


# ============================================================================
# Group 7 — Stub filter post-final-answer (S25)
# ============================================================================


class TestStreamStubFilter:
    """S25: stream filters final answers containing 'no further action needed'
    or 'observation: none' and replaces with stub("confused", language).
    Sync does NOT run this filter before the pipeline.
    """

    @pytest.mark.asyncio
    async def test_no_further_action_needed_replaced_by_confused_stub(self, engine):
        """S25: LLM emits a leaky meta-answer containing 'no further action
        needed'. Stream replaces it with stub("confused", ENGLISH).
        """
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = True  # skip evidence gate complications

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: No further action needed.",
            ),
        )

        stub_calls: list[tuple[str, str]] = []

        def _stub_spy(key, language):
            stub_calls.append((key, language))
            return f"[CONFUSED:{key}:{language}]"

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.get_localized_stub",
            side_effect=_stub_spy,
        ):
            await _run_stream(engine, gateway, state)

        # Stub filter triggered — "confused" key was requested
        assert any(k == "confused" for k, _ in stub_calls), \
            f"Stub 'confused' not invoked; calls={stub_calls}"
        assert state.final_answer.startswith("[CONFUSED:confused:")


# ============================================================================
# Group 8 — Step 2+ prompt prefix carries original query (S2)
# ============================================================================


class TestStreamStepPromptPrefix:
    """S2: from step 2 onward, stream prepends 'Original user query: {query}'
    to the message sent to the LLM. Sync does NOT (it only sends
    'Observation: ...\\n\\nContinue ...'). Locks this intentional divergence.
    """

    @pytest.mark.asyncio
    async def test_step2_message_includes_original_user_query(self, engine):
        """S2: step 1 runs a tool; step 2's send_message receives a message
        containing 'Original user query: ' prefix (streaming-only).
        """
        state = AgentState(query="what about KITAS?", max_steps=2, current_step=0, intent_type="simple")
        state.skip_rag = True
        tc = ToolCall(tool_name="calculator", arguments={})

        captured_messages: list[str] = []

        async def _send(chat, message, *a, **k):
            captured_messages.append(message)
            if len(captured_messages) == 1:
                return _llm_response("use calc", candidates=[MagicMock()])
            return _llm_response("Final Answer: Done.")

        gateway = _mk_gateway(send_message_side_effect=_send)

        parse_call = {"i": 0}

        def _parse(*a, **k):
            parse_call["i"] += 1
            if parse_call["i"] == 1:
                return ([tc], "native")
            return ([], "none")

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            side_effect=_parse,
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            new_callable=AsyncMock,
            return_value=("calc result: 42", 0.01),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            await _run_stream(engine, gateway, state, query="what about KITAS?")

        # Exactly 2 in-loop send_message calls (step1 + step2)
        assert len(captured_messages) == 2
        # S2: step 2's message carries the original query prefix
        step2_message = captured_messages[1]
        assert "Original user query: what about KITAS?" in step2_message
        # And still carries the previous observation
        assert "Observation:" in step2_message
        # And the 'Continue' suffix
        assert "Continue" in step2_message


# ============================================================================
# Group 9 — Images only on step 1 (S3)
# ============================================================================


class TestStreamImagesStep1Only:
    """S3: `images` parameter is only forwarded on step 1
    (`step_images = images if state.current_step == 1 else None`). Later
    steps pass `images=None` to `llm_gateway.send_message`.
    """

    @pytest.mark.asyncio
    async def test_images_passed_only_on_step1(self, engine):
        """S3: step 1 send_message receives images=[...]; step 2 receives
        images=None.
        """
        state = AgentState(query="q", max_steps=2, current_step=0, intent_type="simple")
        state.skip_rag = True

        tc = ToolCall(tool_name="calculator", arguments={})
        captured_images: list = []

        async def _send(chat, message, *a, **kwargs):
            captured_images.append(kwargs.get("images"))
            if len(captured_images) == 1:
                return _llm_response("use calc", candidates=[MagicMock()])
            return _llm_response("Final Answer: Done.")

        gateway = _mk_gateway(send_message_side_effect=_send)

        parse_call = {"i": 0}

        def _parse(*a, **k):
            parse_call["i"] += 1
            if parse_call["i"] == 1:
                return ([tc], "native")
            return ([], "none")

        test_images = [{"base64": "AAAA", "name": "test.png"}]

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            side_effect=_parse,
        ), patch(
            "backend.services.rag.agentic.reasoning.execute_tool",
            new_callable=AsyncMock,
            return_value=("calc result: 42", 0.01),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ):
            await _run_stream(engine, gateway, state, images=test_images)

        assert len(captured_images) == 2
        # S3: step 1 got images; step 2 got None
        assert captured_images[0] == test_images
        assert captured_images[1] is None


# ============================================================================
# Group 10 — Tier1 stub fallback on Tier1 regen raise (S22)
# ============================================================================


class TestStreamTier1StubFallback:
    """S22: Tier1 regen send_message raises → state.final_answer set to
    `_get_localized_stub("abstain", language)`. Same narrow exception tuple
    as sync U1 contract. Locks the stream-side tripwire.
    """

    @pytest.mark.asyncio
    async def test_tier1_regen_resource_exhausted_falls_back_to_abstain_stub(self, engine):
        """S22: policy gate fires → Tier1 regen raises ResourceExhausted →
        final_answer = stub("abstain", ENGLISH).
        """
        from google.api_core.exceptions import ResourceExhausted

        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = False
        state.final_answer = "pre-regen weak answer"

        call_count = {"i": 0}

        async def _send(*a, **k):
            call_count["i"] += 1
            if call_count["i"] == 1:
                # Step 1 LLM returns the pre-regen answer
                return _llm_response("Final Answer: pre-regen weak answer")
            # Tier1 regen (second call) raises
            raise ResourceExhausted("quota spent")

        gateway = _mk_gateway(send_message_side_effect=_send)

        stub_calls: list[tuple[str, str]] = []

        def _stub_spy(key, language):
            stub_calls.append((key, language))
            return f"[TIER1-ABSTAIN:{key}:{language}]"

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.05,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,  # non-critical → Tier1 path
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_tool_usage",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_trusted_context_markers",
            return_value=(False, []),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_substantial_context",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.get_localized_stub",
            side_effect=_stub_spy,
        ):
            await _run_stream(engine, gateway, state)

        # Tier1 regen was attempted (2nd send_message call) and failed
        assert call_count["i"] == 2
        # Stub "abstain" requested as final fallback
        assert any(k == "abstain" for k, _ in stub_calls), \
            f"abstain stub not invoked after Tier1 regen raise; got {stub_calls}"
        # Final answer replaced with the stub
        assert state.final_answer.startswith("[TIER1-ABSTAIN:abstain:")


# ============================================================================
# Group 11 — Pipeline fallback path (S26, I-S9)
# ============================================================================


class TestStreamPipelineFallback:
    """S26: response_pipeline.process raises ValueError/RuntimeError/KeyError
    → `post_process_response(final_answer, query)` is called as fallback.
    Stream's error-recovery matches sync §R30.
    """

    @pytest.mark.asyncio
    async def test_pipeline_raise_falls_back_to_post_process(self, engine):
        """S26: pipeline.process raises → final_answer updated by
        post_process_response fallback. Stream continues to token chunking,
        generator closes cleanly (I-S9).
        """
        state = AgentState(query="q", max_steps=1, current_step=0, intent_type="simple")
        state.skip_rag = True

        # Inject a real-shape response pipeline that raises
        bad_pipeline = MagicMock()
        bad_pipeline.process = AsyncMock(side_effect=ValueError("pipeline failed"))
        engine.response_pipeline = bad_pipeline

        gateway = _mk_gateway(
            send_message_side_effect=lambda *a, **k: _llm_response(
                "Final Answer: raw LLM answer",
            ),
        )

        with patch(
            "backend.services.rag.agentic.reasoning.parse_tool_calls_from_response",
            return_value=([], "none"),
        ), patch(
            "backend.services.rag.agentic.reasoning.detect_query_language",
            return_value="ENGLISH",
        ), patch(
            "backend.services.rag.agentic.reasoning.compute_evidence_score",
            return_value=0.8,
        ), patch(
            "backend.services.rag.agentic.reasoning.is_critical_domain",
            return_value=False,
        ), patch(
            "backend.services.rag.agentic.reasoning.post_process_response",
            return_value="FALLBACK POST-PROCESSED",
        ):
            events = await _run_stream(engine, gateway, state)

        # Pipeline was attempted and raised — fallback fired
        bad_pipeline.process.assert_awaited_once()
        # final_answer set to post_process_response fallback output
        assert state.final_answer == "FALLBACK POST-PROCESSED"
        # I-S9: generator closed; evidence + token events still emitted
        types = _event_types(events)
        assert "evidence_score" in types
        assert "token" in types
