"""
Tests for parse_tool_calls_from_response — regex_degraded OpenRouter fallback.

These tests exercise the third pass that activates when native function-call
parsing and the plain regex fallback both fail, typically because OpenRouter
double-wraps tool_call payloads in nested ```json``` fences or buries them in
surrounding prose.

The tests deliberately use the real ``is_valid_tool_call`` contract
(requires ``.tool_name`` + ``.arguments`` on the returned object) and the
real ``ToolCall`` dataclass. Only ``parse_tool_call`` is patched — to
stand in for the ReAct-style ``ACTION: tool(...)`` regex parser — because
the degraded path now builds the ``ToolCall`` directly from the isolated
JSON rather than delegating back to ``parse_tool_call``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from backend.services.rag.agentic._reasoning_loop_helpers import (
    parse_tool_calls_from_response,
)
from backend.services.tools.definitions import ToolCall


_VALID_TOOL_JSON = '{"tool_name": "vector_search", "tool_input": {"query": "bali kitas"}}'


def _fake_parse_tool_call(payload: Any, use_native: bool = False) -> Any:
    """Stand-in for reasoning.parse_tool_call.

    The real parser handles two shapes:
      - native Gemini ``part`` objects (``use_native=True``);
      - ReAct text like ``ACTION: tool(args)`` (``use_native=False``).

    Neither branch of the real parser recognises OpenRouter's
    ``{"tool_name": ..., "tool_input": ...}`` JSON shape, so we return
    ``None`` unconditionally. That forces the helper down to the
    ``regex_degraded`` pass, which now builds a ``ToolCall`` from the JSON
    directly — exactly what happens in production.
    """
    return None


@pytest.fixture
def patched_reasoning() -> Iterator[None]:
    """Patch ``parse_tool_call`` on the reasoning module.

    The helper resolves it lazily via
    ``from backend.services.rag.agentic import reasoning as _reasoning_module``,
    so patching the attribute on the module object is what the lazy lookup
    sees at call time. ``is_valid_tool_call`` is NOT patched: we want the
    real attribute-based validator to run against the ``ToolCall`` built
    by the degraded pass, matching production semantics.
    """
    import backend.services.rag.agentic.reasoning as reasoning_module

    with patch.object(
        reasoning_module, "parse_tool_call", side_effect=_fake_parse_tool_call,
    ):
        yield


class _NoCandidatesResponse:
    """Minimal response_obj whose ``candidates`` attribute is falsy, forcing
    the helper to skip the native path and rely on the text fallback."""

    candidates: list[Any] = []


def test_parse_regex_degraded_nested_fences(patched_reasoning: None) -> None:
    """Double-wrapped ```json``` fences (OpenRouter quirk) must be unwrapped
    before the brace-balanced scan finds the tool_call object."""
    text_response = (
        "```json\n"
        "```json\n"
        f"{_VALID_TOOL_JSON}\n"
        "```\n"
        "```"
    )
    tool_calls, mode = parse_tool_calls_from_response(
        response_obj=_NoCandidatesResponse(),
        text_response=text_response,
    )

    assert mode == "regex_degraded"
    assert len(tool_calls) == 1
    assert isinstance(tool_calls[0], ToolCall)
    assert tool_calls[0].tool_name == "vector_search"
    assert tool_calls[0].arguments == {"query": "bali kitas"}


def test_parse_regex_degraded_trailing_prose(patched_reasoning: None) -> None:
    """The degraded pass should still extract the tool_call when prose sits
    both before and after the JSON object in the model output."""
    text_response = (
        "Some reasoning before the call.\n"
        f"{_VALID_TOOL_JSON}\n"
        "Some trailing thoughts that include {stray braces} and \"quotes\"."
    )
    tool_calls, mode = parse_tool_calls_from_response(
        response_obj=_NoCandidatesResponse(),
        text_response=text_response,
    )

    assert mode == "regex_degraded"
    assert len(tool_calls) == 1
    assert isinstance(tool_calls[0], ToolCall)
    assert tool_calls[0].tool_name == "vector_search"


def test_parse_still_returns_none_when_no_tool_call(patched_reasoning: None) -> None:
    """Garbage input with no recoverable tool_call must fall through to
    ``"none"`` — degraded must not invent a call from unrelated braces."""
    text_response = (
        "I could not answer this query because the retrieval tool is down. "
        "Here is an unrelated JSON snippet: {\"status\": \"error\"} and "
        "some trailing prose."
    )
    tool_calls, mode = parse_tool_calls_from_response(
        response_obj=_NoCandidatesResponse(),
        text_response=text_response,
    )

    assert tool_calls == []
    assert mode == "none"
