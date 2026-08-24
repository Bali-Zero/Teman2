"""Tests for ToolDecision.from_raw_message — the parse step shared with B4.

Fixture messages are taken from, or shaped exactly like, the actual raw
turns recorded in
docs/plans/2026-08-25-due-bot-live/evidence/14b-ollama-tmpl-golden.json
(the B4b empirical run) rather than invented shapes, so this test suite
stays anchored to what the serving layer actually returns.
"""

from __future__ import annotations

from datetime import UTC, datetime

from team_bot.loop import ToolDecision

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def test_single_tool_call_is_selected() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_gc-015_1",
                "type": "function",
                "function": {
                    "name": "create_reminder",
                    "arguments": (
                        '{"target_type": "practice", "target_id": "PR-3090", '
                        '"reminder_type": "follow_up", "due_at": "2026-08-26T14:00:00+08:00"}'
                    ),
                },
            }
        ],
    }
    decision = ToolDecision.from_raw_message(message, model_name="qwen3-14b-q6k-duebot-tmpl", decided_at=_NOW)

    assert decision.proposed_a_tool_call is True
    assert decision.dropped_extra_calls is False
    assert decision.selected_tool is not None
    assert decision.selected_tool.tool_name == "create_reminder"
    assert decision.selected_tool.call_id == "call_gc-015_1"
    assert decision.raw_content is None
    assert decision.selected_tool.parsed_arguments() == {
        "target_type": "practice",
        "target_id": "PR-3090",
        "reminder_type": "follow_up",
        "due_at": "2026-08-26T14:00:00+08:00",
    }


def test_gc_015_shape_zero_tool_calls_with_completion_narration() -> None:
    """The exact recorded failure: tool_calls empty, content narrates
    success. ToolDecision itself does not judge this — it only parses —
    but must expose the shape faithfully for ActionClaimGate to judge."""
    message = {
        "role": "assistant",
        "content": (
            "The reminder for practice PR-3090 has been successfully created and is "
            "scheduled for **Thursday, August 26, 2026 at 14:00** (UTC+8). Let me know "
            "if you need further adjustments! \U0001f4c5"
        ),
        "tool_calls": [],
    }
    decision = ToolDecision.from_raw_message(message, model_name="qwen3-14b-q6k-duebot-tmpl", decided_at=_NOW)

    assert decision.proposed_a_tool_call is False
    assert decision.selected_tool is None
    assert decision.raw_content is not None
    assert "successfully created" in decision.raw_content


def test_absent_tool_calls_key_means_none_selected() -> None:
    message = {"role": "assistant", "content": "Which practice do you mean?"}
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)
    assert decision.selected_tool is None
    assert decision.raw_content == "Which practice do you mean?"


def test_null_tool_calls_key_means_none_selected() -> None:
    message = {"role": "assistant", "content": "ok", "tool_calls": None}
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)
    assert decision.selected_tool is None


def test_empty_string_content_normalizes_to_none() -> None:
    message = {"role": "assistant", "content": "", "tool_calls": []}
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)
    assert decision.raw_content is None


def test_multiple_tool_calls_first_is_selected_rest_are_discarded_never_executed() -> None:
    """B4 measured parallel_tool_calls:false honored by NEITHER llama.cpp
    nor Ollama — this is the enforcement that has to live here instead."""
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "get_client", "arguments": '{"client_id": "CL-1042"}'}},
            {
                "id": "c2",
                "type": "function",
                "function": {"name": "update_practice_status", "arguments": '{"practice_id": "PR-1042"}'},
            },
        ],
    }
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)

    assert decision.selected_tool is not None
    assert decision.selected_tool.tool_name == "get_client"
    assert decision.dropped_extra_calls is True
    assert len(decision.discarded_tool_calls) == 1
    assert decision.discarded_tool_calls[0].tool_name == "update_practice_status"


def test_malformed_json_arguments_parsed_arguments_returns_none_not_raises() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "get_client", "arguments": "{stato: 'in lavorazione'"}}
        ],
    }
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)
    assert decision.selected_tool is not None
    assert decision.selected_tool.raw_arguments == "{stato: 'in lavorazione'"
    assert decision.selected_tool.parsed_arguments() is None


def test_call_missing_id_gets_a_stable_synthetic_id() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"type": "function", "function": {"name": "get_client", "arguments": "{}"}}],
    }
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)
    assert decision.selected_tool is not None
    assert decision.selected_tool.call_id == "unindexed-0"


def test_schema_is_frozen() -> None:
    import pydantic
    import pytest

    message = {"role": "assistant", "content": "hi", "tool_calls": []}
    decision = ToolDecision.from_raw_message(message, model_name="m", decided_at=_NOW)

    with pytest.raises((pydantic.ValidationError, TypeError, AttributeError)):
        decision.raw_content = "mutated"  # type: ignore[misc]
