"""compose_reply — the structural fix for gc-015's defect class.

This is the PRIMARY control (claim_gate.py is now defense-in-depth only —
see that module's docstring). The tests below assert the actual claim: in
the MUTATION branch, model_content is NEVER the reply source, regardless of
what it says — the lie is unconstructible, not merely undetected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from team_bot.confirmation.models import PendingAction, PendingActionStatus
from team_bot.confirmation.outcomes import ConfirmationOutcome, Locale
from team_bot.confirmation.reply_composer import ComposedReply, ReadChainOutcome, TurnIntent, compose_reply
from team_bot.confirmation.store import ProposeOutcome
from team_bot.loop.execution_record import ExecutionRecord, ExecutionSource
from team_bot.loop.tool_decision import ToolDecision

_NOW = datetime(2026, 8, 25, 10, 0, 0, tzinfo=UTC)

# The EXACT string gc-015 recorded (B4b golden suite, both serving stacks) —
# docs/plans/2026-08-25-due-bot-live/evidence/14b-ollama-tmpl-golden.json,
# .results[14].detail.actual_content. Model returned ZERO tool_calls and
# this content narrating a completed mutation that never happened.
_GC_015_LYING_CONTENT = (
    "The reminder for practice PR-3090 has been successfully created and is "
    "scheduled for **Thursday, August 26, 2026 at 14:00** (UTC+8). "
    "Let me know if you need further adjustments! \U0001f4c5"
)


def _action(**overrides: object) -> PendingAction:
    kwargs: dict[str, object] = {
        "short_code": "7F3K",
        "principal_id": "USR-1",
        "tool_name": "create_reminder",
        "encrypted_args": b"ciphertext",
        "args_sha256": "a" * 64,
        "idempotency_key": "b" * 64,
        "status": PendingActionStatus.PROPOSED,
        "leader_epoch": 0,
        "proposed_at": _NOW,
        "expires_at": _NOW + timedelta(minutes=5),
    }
    kwargs.update(overrides)
    return PendingAction(**kwargs)


def _tool_decision(*, proposed_a_tool_call: bool = False, raw_content: str | None = None) -> ToolDecision:
    from team_bot.loop.tool_decision import ProposedToolCall

    selected = (
        ProposedToolCall(call_id="call_1", tool_name="create_reminder", raw_arguments="{}")
        if proposed_a_tool_call
        else None
    )
    return ToolDecision(
        selected_tool=selected,
        raw_content=raw_content,
        model_name="test-model",
        decided_at=_NOW,
    )


# ── gc-015 reproduction (mandatory) ─────────────────────────────────────


def test_gc_015_lying_content_is_never_the_reply_for_a_mutation_turn() -> None:
    """The exact reproduction: MUTATION intent, the model's verbatim lying
    content, nothing structured (no confirmation_outcome, no
    execution_record) — gc-015's exact shape. The lie must be structurally
    unreachable as the reply, not merely caught by a detector."""
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content=_GC_015_LYING_CONTENT,
        confirmation_outcome=None,
        action=None,
        execution_record=None,
    )
    assert reply.source != "model_content"
    assert reply.source == "fallback"
    assert _GC_015_LYING_CONTENT not in reply.text
    assert "PR-3090" not in reply.text
    assert "successfully created" not in reply.text


def test_gc_015_reproduction_is_deterministic_across_repeated_calls() -> None:
    """No randomness, no model call — same input, same output, every time."""
    kwargs = dict(
        turn_intent=TurnIntent.MUTATION,
        model_content=_GC_015_LYING_CONTENT,
        confirmation_outcome=None,
        action=None,
        execution_record=None,
    )
    first = compose_reply(**kwargs)
    second = compose_reply(**kwargs)
    assert first == second


# ── branch 1: confirmation_outcome always wins ──────────────────────────


def test_confirmation_outcome_wins_even_with_lying_model_content_present() -> None:
    """Branch 1 must win regardless of turn_intent or model_content — F6's
    own state machine reporting what happened is the strongest possible
    grounding."""
    action = _action()
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,  # deliberately the "wrong" intent
        model_content=_GC_015_LYING_CONTENT,  # deliberately a lie
        confirmation_outcome=outcome,
        action=action,
    )
    assert reply.source == "template"
    assert reply.text == "Got it — reply CONFERMA 7F3K within 5 minutes to run create_reminder."
    assert _GC_015_LYING_CONTENT not in reply.text


def test_confirmation_outcome_respects_locale() -> None:
    action = _action()
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content=None,
        confirmation_outcome=outcome,
        action=action,
        locale=Locale.IT,
    )
    assert reply.source == "template"
    assert "Ricevuto" in reply.text


# ── branch 2: MUTATION always composes from structure ───────────────────


def test_mutation_with_a_successful_execution_record_is_grounded_not_model_content() -> None:
    record = ExecutionRecord(
        tool_name="create_reminder",
        ok=True,
        source=ExecutionSource.PENDING_ACTION,
        executed_at=_NOW,
        result_ref="AUD-1",
    )
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content=_GC_015_LYING_CONTENT,  # still a lie, still ignored
        confirmation_outcome=None,
        action=None,
        execution_record=record,
    )
    assert reply.source == "template"
    assert "create_reminder" in reply.text
    assert _GC_015_LYING_CONTENT not in reply.text


def test_mutation_with_a_failed_execution_record_says_it_failed_not_succeeded() -> None:
    record = ExecutionRecord(
        tool_name="create_reminder",
        ok=False,
        source=ExecutionSource.PENDING_ACTION,
        executed_at=_NOW,
    )
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content=_GC_015_LYING_CONTENT,
        confirmation_outcome=None,
        action=None,
        execution_record=record,
    )
    assert reply.source == "template"
    assert "didn't complete" in reply.text or "failed" in reply.text
    assert "successfully" not in reply.text.lower()


def test_mutation_with_nothing_structured_uses_the_fixed_fallback_sentence() -> None:
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content="anything at all, even innocuous",
        confirmation_outcome=None,
        action=None,
        execution_record=None,
    )
    assert reply.source == "fallback"
    assert reply.text == (
        "I wasn't able to complete that automatically — could you confirm the request again?"
    )


def test_mutation_never_returns_model_content_even_when_model_content_is_none() -> None:
    """Branch 2 does not require model_content at all — a None model_content
    still produces a valid fallback, proving this branch's behavior is
    entirely independent of what (if anything) the model said."""
    reply = compose_reply(
        turn_intent=TurnIntent.MUTATION,
        model_content=None,
        confirmation_outcome=None,
        action=None,
        execution_record=None,
    )
    assert reply.source == "fallback"


# ── branch 3: READ_OR_NONE — model_content with ActionClaimGate as net ──


def test_read_or_none_innocent_content_passes_through() -> None:
    innocent = "The practice PR-3090 is currently in doc_collection status."
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=innocent,
        confirmation_outcome=None,
        action=None,
        tool_decision=_tool_decision(proposed_a_tool_call=False, raw_content=innocent),
    )
    assert reply.source == "model_content"
    assert reply.text == innocent


def test_read_or_none_content_that_claims_completion_is_blocked_and_falls_back() -> None:
    """The last-resort net: the upstream router misclassified a MUTATION
    turn as READ_OR_NONE, and the model's free text claims a completion
    ActionClaimGate can still catch (defense-in-depth, per claim_gate.py's
    docstring)."""
    claiming = "I created the reminder for you."
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=claiming,
        confirmation_outcome=None,
        action=None,
        tool_decision=_tool_decision(proposed_a_tool_call=False, raw_content=claiming),
    )
    assert reply.source == "fallback"
    assert reply.text != claiming
    assert "created" not in reply.text.lower()


def test_read_or_none_with_a_grounded_execution_record_allows_completion_language() -> None:
    """When a tool DID execute this turn (ExecutionRecord.ok=True), the
    claim gate ALLOWs completion language even in the READ_OR_NONE branch —
    it is genuinely grounded, not a lie."""
    record = ExecutionRecord(
        tool_name="create_reminder",
        ok=True,
        source=ExecutionSource.DIRECT_R1,
        executed_at=_NOW,
        result_ref="AUD-2",
    )
    grounded = "I created the reminder for you."
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=grounded,
        confirmation_outcome=None,
        action=None,
        execution_record=record,
        tool_decision=_tool_decision(proposed_a_tool_call=True, raw_content=grounded),
    )
    assert reply.source == "model_content"
    assert reply.text == grounded


def test_read_or_none_missing_tool_decision_raises() -> None:
    """The claim gate needs a ToolDecision to phrase its BLOCK reason —
    compose_reply must fail loudly, not silently skip the gate."""
    with pytest.raises(ValueError):
        compose_reply(
            turn_intent=TurnIntent.READ_OR_NONE,
            model_content="anything",
            confirmation_outcome=None,
            action=None,
        )


def test_read_or_none_with_model_content_none_falls_back_without_calling_the_gate() -> None:
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=None,
        action=None,
    )
    assert reply.source == "fallback"


# ── the 4th template: ReadChainOutcome (directive #1 §2 follow-up) ──────


def test_budget_exhausted_gets_its_own_dedicated_text_not_the_claim_gate_fallback() -> None:
    """The whole point of this fix: reporting the CORRECT reason. A chain
    that ran out of steps must not say 'I want to make sure I get this
    right' (that sentence is for an ActionClaimGate BLOCK, a different
    fact) — it must say it ran out of steps."""
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=None,
        action=None,
        read_chain_outcome=ReadChainOutcome.BUDGET_EXHAUSTED,
    )
    assert reply.source == "template"
    assert "steps" in reply.text
    assert reply.text != (
        "I want to make sure I get this right — could you tell me a bit more about what you need?"
    )


def test_stuck_loop_gets_different_text_from_budget_exhausted() -> None:
    """Two distinct true causes must not collapse into one reported
    reason — the exact mistake this fix exists to stop making, applied to
    its own two new cases."""
    budget = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=None,
        action=None,
        read_chain_outcome=ReadChainOutcome.BUDGET_EXHAUSTED,
    )
    stuck = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=None,
        action=None,
        read_chain_outcome=ReadChainOutcome.STUCK_LOOP,
    )
    assert budget.text != stuck.text
    assert "repeating" in stuck.text


def test_read_chain_outcome_wins_over_model_content() -> None:
    """A definitive, structurally-known termination reason must not be
    overridden by whatever (if anything) the model's raw content says —
    same "strongest grounding wins" principle as confirmation_outcome and
    execution_record."""
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content="Here is what I found: ...",
        confirmation_outcome=None,
        action=None,
        read_chain_outcome=ReadChainOutcome.BUDGET_EXHAUSTED,
    )
    assert reply.source == "template"
    assert "Here is what I found" not in reply.text


def test_confirmation_outcome_still_wins_over_read_chain_outcome() -> None:
    """Branch order: confirmation_outcome (F6's own state machine) is
    still the single strongest signal, even paired with a read_chain
    termination reason."""
    action = _action()
    outcome = ConfirmationOutcome.from_propose(ProposeOutcome.CREATED)
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=outcome,
        action=action,
        read_chain_outcome=ReadChainOutcome.STUCK_LOOP,
    )
    assert reply.source == "template"
    assert reply.text == "Got it — reply CONFERMA 7F3K within 5 minutes to run create_reminder."


def test_read_chain_outcome_rejects_mutation_intent_as_a_contract_violation() -> None:
    """A chain that ended via budget exhaustion or a stuck-loop verdict
    never reached a mutation proposal this turn by construction — pairing
    the two is a caller bug, not a real shape to render text for."""
    with pytest.raises(ValueError, match="are contradictory"):
        compose_reply(
            turn_intent=TurnIntent.MUTATION,
            model_content=None,
            confirmation_outcome=None,
            action=None,
            read_chain_outcome=ReadChainOutcome.BUDGET_EXHAUSTED,
        )


def test_read_chain_outcome_respects_locale() -> None:
    reply = compose_reply(
        turn_intent=TurnIntent.READ_OR_NONE,
        model_content=None,
        confirmation_outcome=None,
        action=None,
        read_chain_outcome=ReadChainOutcome.BUDGET_EXHAUSTED,
        locale=Locale.IT,
    )
    assert "passaggi" in reply.text


def test_read_chain_outcome_has_exactly_the_two_documented_members() -> None:
    assert {member.value for member in ReadChainOutcome} == {"budget_exhausted", "stuck_loop"}


# ── ComposedReply itself ─────────────────────────────────────────────────


def test_composed_reply_is_frozen_and_extra_forbidden() -> None:
    reply = ComposedReply(text="hello", source="template")
    with pytest.raises(ValidationError):
        reply.text = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ComposedReply(text="hello", source="template", extra_field="nope")  # type: ignore[call-arg]


def test_composed_reply_source_is_a_closed_literal() -> None:
    with pytest.raises(ValidationError):
        ComposedReply(text="hello", source="model_hallucination")  # type: ignore[arg-type]


# ── TurnIntent — consumption contract sanity ─────────────────────────────


def test_turn_intent_has_exactly_the_two_documented_members() -> None:
    assert {member.value for member in TurnIntent} == {"mutation", "read_or_none"}
