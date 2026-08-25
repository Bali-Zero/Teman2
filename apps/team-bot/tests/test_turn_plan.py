"""Tests for turn_plan.py — the structural type split (directive #1 §2)
that lets reads/searches chain freely while making "one mutation per
turn" unrepresentable-if-violated.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from team_bot.loop import (
    ABSOLUTE_MAX_READ_STEPS,
    FinalAnswer,
    MutationDecision,
    ReadPlan,
    ReadStep,
    ReadStepOutcome,
    StepClassification,
    ToolDecision,
    UnknownToolError,
    classify_step,
    try_append_read_step,
)

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _decision(tool_name: str | None, *, args: str = "{}", content: str | None = None) -> ToolDecision:
    if tool_name is None:
        message = {"role": "assistant", "content": content, "tool_calls": []}
    else:
        message = {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": tool_name, "arguments": args}}
            ],
        }
    return ToolDecision.from_raw_message(message, model_name="qwen3-14b-q6k-duebot-tmpl", decided_at=_NOW)


# ---------------------------------------------------------------------------
# classify_step
# ---------------------------------------------------------------------------


def test_classify_read_tool() -> None:
    assert classify_step(_decision("search_clients", args='{"query": "John"}')) == StepClassification.READ


def test_classify_mutation_tool() -> None:
    assert classify_step(_decision("create_reminder")) == StepClassification.MUTATION


def test_classify_no_tool_call_is_final() -> None:
    assert classify_step(_decision(None, content="Which practice do you mean?")) == StepClassification.FINAL


def test_classify_unknown_tool_name() -> None:
    assert classify_step(_decision("delete_everything")) == StepClassification.UNKNOWN_TOOL


# ---------------------------------------------------------------------------
# ReadStep / ReadPlan construction
# ---------------------------------------------------------------------------


def test_read_step_from_tool_decision() -> None:
    decision = _decision("get_client", args='{"client_id": "CL-1042"}')
    step = ReadStep.from_tool_decision(decision, step_index=0)
    assert step.call.tool_name == "get_client"
    assert step.step_index == 0


def test_read_step_rejects_mutation_tool() -> None:
    decision = _decision("open_practice")
    with pytest.raises(ValueError, match="ReadStep only represents a read call"):
        ReadStep.from_tool_decision(decision, step_index=0)


def test_read_step_rejects_unknown_tool() -> None:
    decision = _decision("teleport_client")
    with pytest.raises(UnknownToolError):
        ReadStep.from_tool_decision(decision, step_index=0)


def test_read_step_rejects_no_selected_tool() -> None:
    decision = _decision(None, content="hi")
    with pytest.raises(ValueError, match="no selected_tool"):
        ReadStep.from_tool_decision(decision, step_index=0)


def test_read_plan_start_and_appended() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    d2 = _decision("get_client", args='{"client_id": "CL-1042"}')
    plan = ReadPlan.start(ReadStep.from_tool_decision(d1, step_index=0))
    assert len(plan.steps) == 1
    plan = plan.appended(ReadStep.from_tool_decision(d2, step_index=1))
    assert len(plan.steps) == 2
    assert [s.call.tool_name for s in plan.steps] == ["search_clients", "get_client"]


def test_read_plan_start_requires_step_index_zero() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    step = ReadStep.from_tool_decision(d1, step_index=1)
    with pytest.raises(ValueError, match="must start with step_index 0"):
        ReadPlan.start(step)


def test_read_plan_appended_requires_contiguous_index() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    d2 = _decision("get_client", args='{"client_id": "CL-1042"}')
    plan = ReadPlan.start(ReadStep.from_tool_decision(d1, step_index=0))
    out_of_order = ReadStep.from_tool_decision(d2, step_index=5)
    with pytest.raises(ValueError, match="expected the next step to carry step_index=1"):
        plan.appended(out_of_order)


def test_read_plan_rejects_empty_construction() -> None:
    with pytest.raises(ValidationError):
        ReadPlan(steps=())


def test_read_plan_model_validator_rejects_non_contiguous_direct_construction() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    d2 = _decision("get_client", args='{"client_id": "CL-1042"}')
    step0 = ReadStep.from_tool_decision(d1, step_index=0)
    step_wrong = ReadStep.from_tool_decision(d2, step_index=7)
    with pytest.raises(ValidationError, match="contiguous"):
        ReadPlan(steps=(step0, step_wrong))


def test_read_plan_hard_ceiling_is_absolute_max_read_steps() -> None:
    """Even a direct construction (bypassing try_append_read_step
    entirely) cannot exceed the structural ceiling."""
    steps = tuple(
        ReadStep.from_tool_decision(_decision("get_client", args=f'{{"client_id": "CL-{i:04d}"}}'), step_index=i)
        for i in range(ABSOLUTE_MAX_READ_STEPS + 1)
    )
    with pytest.raises(ValidationError):
        ReadPlan(steps=steps)


def test_read_plan_is_frozen() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    plan = ReadPlan.start(ReadStep.from_tool_decision(d1, step_index=0))
    with pytest.raises((ValidationError, TypeError)):
        plan.steps = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# try_append_read_step — the loop's actual per-step entry point
# ---------------------------------------------------------------------------


def test_try_append_read_step_starts_a_plan_from_none() -> None:
    decision = _decision("search_clients", args='{"query": "John"}')
    result = try_append_read_step(None, decision, max_steps=3)
    assert result.outcome == ReadStepOutcome.APPENDED
    assert len(result.plan.steps) == 1


def test_try_append_read_step_grows_an_existing_plan() -> None:
    d1 = _decision("search_clients", args='{"query": "John"}')
    d2 = _decision("get_client", args='{"client_id": "CL-1042"}')
    r1 = try_append_read_step(None, d1, max_steps=3)
    r2 = try_append_read_step(r1.plan, d2, max_steps=3)
    assert r2.outcome == ReadStepOutcome.APPENDED
    assert len(r2.plan.steps) == 2


def test_try_append_read_step_reports_budget_exhausted_typed_not_raised() -> None:
    """Golden fixture team.tool-step-exhaustion's own wording: 'a bounded,
    typed "ran out of steps" outcome — never silently keep going or
    crash.' This must be a returned value, not an exception."""
    plan = None
    calls = [
        _decision("search_clients", args='{"query": "A"}'),
        _decision("search_clients", args='{"query": "B"}'),
    ]
    for call in calls:
        result = try_append_read_step(plan, call, max_steps=2)
        assert result.outcome == ReadStepOutcome.APPENDED
        plan = result.plan

    one_too_many = _decision("search_clients", args='{"query": "C"}')
    exhausted = try_append_read_step(plan, one_too_many, max_steps=2)
    assert exhausted.outcome == ReadStepOutcome.BUDGET_EXHAUSTED
    # The plan is returned UNCHANGED — the rejected step never got in.
    assert len(exhausted.plan.steps) == 2
    assert exhausted.plan is plan


def test_try_append_read_step_with_max_steps_one_matches_todays_behavior() -> None:
    """The dark-flag-off default (team_bot.flags.max_read_steps() == 1
    when TEAM_BOT_MULTISTEP_READS_ENABLED is unset) must behave exactly
    like a single-step world: the first read succeeds, a second is
    BUDGET_EXHAUSTED."""
    d1 = _decision("search_clients", args='{"query": "John"}')
    r1 = try_append_read_step(None, d1, max_steps=1)
    assert r1.outcome == ReadStepOutcome.APPENDED

    d2 = _decision("get_client", args='{"client_id": "CL-1042"}')
    r2 = try_append_read_step(r1.plan, d2, max_steps=1)
    assert r2.outcome == ReadStepOutcome.BUDGET_EXHAUSTED


def test_try_append_read_step_rejects_max_steps_below_one() -> None:
    decision = _decision("search_clients", args='{"query": "John"}')
    with pytest.raises(ValueError, match="max_steps must be >= 1"):
        try_append_read_step(None, decision, max_steps=0)


def test_try_append_read_step_rejects_mutation_call() -> None:
    decision = _decision("open_practice")
    with pytest.raises(ValueError, match="ReadStep only represents a read call"):
        try_append_read_step(None, decision, max_steps=8)


# ---------------------------------------------------------------------------
# MutationDecision — structurally exactly one call
# ---------------------------------------------------------------------------


def test_mutation_decision_from_tool_decision() -> None:
    decision = _decision("open_practice", args='{"client_id": "CL-1042"}')
    mutation = MutationDecision.from_tool_decision(decision)
    assert mutation.call.tool_name == "open_practice"
    assert mutation.preceding_reads is None


def test_mutation_decision_carries_preceding_reads_for_audit_only() -> None:
    read_decision = _decision("get_client", args='{"client_id": "CL-1042"}')
    plan = try_append_read_step(None, read_decision, max_steps=8).plan
    mutation_decision = _decision("update_practice_status")
    mutation = MutationDecision.from_tool_decision(mutation_decision, preceding_reads=plan)
    assert mutation.preceding_reads is plan
    assert len(mutation.preceding_reads.steps) == 1


def test_mutation_decision_has_no_field_that_can_hold_a_second_call() -> None:
    """Structural proof, not a behavioral one: MutationDecision's own
    field set has exactly one call-shaped field ('call': ProposedToolCall),
    and forbids extras — there is no list/tuple field anywhere a second
    call could be smuggled into."""
    fields = MutationDecision.model_fields
    call_shaped = [name for name, info in fields.items() if "ProposedToolCall" in str(info.annotation)]
    assert call_shaped == ["call"]
    assert MutationDecision.model_config.get("extra") == "forbid"


def test_mutation_decision_rejects_read_tool() -> None:
    decision = _decision("get_client", args='{"client_id": "CL-1042"}')
    with pytest.raises(ValueError, match="MutationDecision only represents a mutation call"):
        MutationDecision.from_tool_decision(decision)


def test_mutation_decision_rejects_unknown_tool() -> None:
    decision = _decision("wire_money_directly")
    with pytest.raises(UnknownToolError):
        MutationDecision.from_tool_decision(decision)


def test_mutation_decision_rejects_no_selected_tool() -> None:
    decision = _decision(None, content="ok")
    with pytest.raises(ValueError, match="no selected_tool"):
        MutationDecision.from_tool_decision(decision)


def test_mutation_decision_is_frozen() -> None:
    decision = _decision("open_practice")
    mutation = MutationDecision.from_tool_decision(decision)
    with pytest.raises((ValidationError, TypeError)):
        mutation.call = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FinalAnswer
# ---------------------------------------------------------------------------


def test_final_answer_from_tool_decision() -> None:
    decision = _decision(None, content="Which practice do you mean?")
    answer = FinalAnswer.from_tool_decision(decision)
    assert answer.content == "Which practice do you mean?"
    assert answer.preceding_reads is None


def test_final_answer_rejects_a_decision_that_selected_a_tool() -> None:
    decision = _decision("get_client", args='{"client_id": "CL-1042"}')
    with pytest.raises(ValueError, match="cannot build a FinalAnswer"):
        FinalAnswer.from_tool_decision(decision)


def test_final_answer_carries_preceding_reads() -> None:
    read_decision = _decision("search_clients", args='{"query": "John"}')
    plan = try_append_read_step(None, read_decision, max_steps=8).plan
    final_decision = _decision(None, content="I found two clients named John — which one?")
    answer = FinalAnswer.from_tool_decision(final_decision, preceding_reads=plan)
    assert answer.preceding_reads is plan
