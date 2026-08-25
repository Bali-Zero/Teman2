"""Tests for loop_detector.py — GUILT and INNOCENCE pairs, per
cicatrix-superscar.md family #3 ("guard-over-match / gemello UNDER-match").
A guard shipped with only its guilty case tested is exactly the anti-
pattern that family names; every guilty test below has a paired innocent
test that a naive, wider detector would get wrong.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from team_bot.loop import (
    DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD,
    ReadPlan,
    ReadStep,
    ToolDecision,
    detect_stuck_loop,
    try_append_read_step,
)

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _read_decision(tool_name: str, args: str) -> ToolDecision:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": tool_name, "arguments": args}}],
    }
    return ToolDecision.from_raw_message(message, model_name="qwen3-14b-q6k-duebot-tmpl", decided_at=_NOW)


def _plan_from(calls: list[tuple[str, str]]) -> ReadPlan:
    plan: ReadPlan | None = None
    for index, (tool_name, args) in enumerate(calls):
        step = ReadStep.from_tool_decision(_read_decision(tool_name, args), step_index=index)
        plan = ReadPlan.start(step) if plan is None else plan.appended(step)
    assert plan is not None
    return plan


# ---------------------------------------------------------------------------
# GUILTY — a real stuck loop: default threshold and boundary.
# ---------------------------------------------------------------------------


def test_guilty_three_consecutive_identical_calls_is_stuck() -> None:
    """The concrete failure mode this guard exists for: the model asks the
    exact same question three times in a row with nothing changed."""
    plan = _plan_from(
        [
            ("search_clients", '{"query": "John"}'),
            ("search_clients", '{"query": "John"}'),
            ("search_clients", '{"query": "John"}'),
        ]
    )
    verdict = detect_stuck_loop(plan)
    assert verdict.stuck is True
    assert "search_clients" in verdict.reason


def test_guilty_stuck_run_can_appear_after_earlier_progress() -> None:
    """Progress earlier in the chain does not immunize a later stuck run —
    the detector looks at the TAIL, so a chain that later degenerates into
    repetition is still caught."""
    plan = _plan_from(
        [
            ("search_clients", '{"query": "John"}'),
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
        ]
    )
    assert detect_stuck_loop(plan).stuck is True


def test_guilty_at_exactly_the_threshold_boundary() -> None:
    threshold = 4
    plan = _plan_from([("get_client", '{"client_id": "CL-1042"}')] * threshold)
    assert detect_stuck_loop(plan, consecutive_repeat_threshold=threshold).stuck is True


# ---------------------------------------------------------------------------
# INNOCENT — the team lead's own named case, plus neighbors a wider
# (whole-history or alternating-cycle) detector would wrongly flag.
# ---------------------------------------------------------------------------


def test_innocent_same_client_looked_up_twice_for_two_different_practices() -> None:
    """The team lead's own worked example: get_client(CL-1042) recurs —
    identical arguments both times, by construction — but NOT
    consecutively, because a different practice lookup sits in between.
    A whole-history "has this call repeated at all" detector would wrongly
    flag this; the consecutive-tail rule must not."""
    plan = _plan_from(
        [
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-4091"}'),
        ]
    )
    verdict = detect_stuck_loop(plan)
    assert verdict.stuck is False


def test_innocent_two_consecutive_identical_calls_below_default_threshold() -> None:
    """One deliberate re-check (e.g. after a transient tool error) is
    ordinary — only a run of DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD (3) in a
    row is stuck, not two."""
    assert DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD == 3
    plan = _plan_from(
        [
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_client", '{"client_id": "CL-1042"}'),
        ]
    )
    assert detect_stuck_loop(plan).stuck is False


def test_innocent_alternating_pattern_never_flagged() -> None:
    """A longer alternating cycle (A, B, A, B, A, B) is deliberately NOT
    detected — see the module docstring: catching it would risk flagging
    ordinary multi-entity cross-referencing (check client, check practice,
    check client, check practice, ...) as stuck. Documents the detector's
    known, deliberate scope boundary rather than hiding it."""
    plan = _plan_from(
        [
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
            ("get_client", '{"client_id": "CL-1042"}'),
            ("get_practice", '{"practice_id": "PR-3090"}'),
        ]
    )
    assert detect_stuck_loop(plan).stuck is False


def test_innocent_same_tool_different_arguments_never_flagged() -> None:
    """Same tool called repeatedly with DIFFERENT arguments (a legitimate
    multi-query search session) is never a repeat at all."""
    plan = _plan_from(
        [
            ("search_clients", '{"query": "John"}'),
            ("search_clients", '{"query": "Jonathan"}'),
            ("search_clients", '{"query": "Giovanni"}'),
        ]
    )
    assert detect_stuck_loop(plan).stuck is False


def test_innocent_short_chain_below_threshold_length() -> None:
    plan = _plan_from([("search_clients", '{"query": "John"}')])
    verdict = detect_stuck_loop(plan)
    assert verdict.stuck is False
    assert "fewer than" in verdict.reason


# ---------------------------------------------------------------------------
# Detector configuration guards
# ---------------------------------------------------------------------------


def test_threshold_below_two_is_rejected() -> None:
    plan = _plan_from([("search_clients", '{"query": "John"}')])
    with pytest.raises(ValueError, match="at least 2"):
        detect_stuck_loop(plan, consecutive_repeat_threshold=1)


def test_incrementally_calling_after_each_try_append_read_step() -> None:
    """The realistic call pattern: check after every appended step, not
    just once at the end."""
    plan = None
    verdicts = []
    for tool_name, args in [
        ("get_client", '{"client_id": "CL-1042"}'),
        ("get_client", '{"client_id": "CL-1042"}'),
        ("get_client", '{"client_id": "CL-1042"}'),
    ]:
        result = try_append_read_step(plan, _read_decision(tool_name, args), max_steps=8)
        plan = result.plan
        verdicts.append(detect_stuck_loop(plan).stuck)
    assert verdicts == [False, False, True]
