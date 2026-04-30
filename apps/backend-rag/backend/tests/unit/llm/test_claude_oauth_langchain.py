"""Unit tests for the Claude OAuth LangChain wrapper structured-output shim.

The wrapper at ``backend/llm/claude_oauth_langchain.py`` overrides
``with_structured_output`` because the underlying ``claude -p`` subprocess
has no native tool-calling channel. These tests pin the prompt-engineered
JSON-extraction behaviour so a future change to the override keeps:

- happy-path JSON parses to the Pydantic schema
- markdown-fenced JSON (```json … ```) is unwrapped
- prose-wrapped JSON ("Sure, here is the JSON: { … }") is extracted
- malformed JSON raises ``json.JSONDecodeError`` (caller handles the
  fallback in ``understand_query_node``)
- schema violations raise ``pydantic.ValidationError``
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError


pytest.importorskip("langchain_core")


class _Sample(BaseModel):
    intent: str = Field(...)
    confidence: float = Field(default=0.0)


def _make_model_with_response(text: str):
    """Patch ``complete_async`` so building the wrapper is hermetic."""
    from unittest.mock import AsyncMock, patch

    from backend.llm import claude_oauth_langchain as mod

    fake_resp = type("R", (), {"text": text})()
    return patch.object(
        mod,
        "complete_async",
        AsyncMock(return_value=fake_resp),
    )


def test_with_structured_output_returns_runnable():
    """The wrapper must be a real LangChain Runnable.

    Cross-LLM review (Codex + Gemini, 2/2 confluence) flagged that a plain
    class with `invoke` / `ainvoke` would crash LangGraph orchestration the
    moment it tried to inject callbacks via `with_config(...)`.
    """
    from langchain_core.runnables import Runnable

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    model = build_claude_oauth_chat_model()
    structured = model.with_structured_output(_Sample)

    assert isinstance(structured, Runnable)
    # Smoke-test the config injection path that LangGraph relies on.
    configured = structured.with_config({"tags": ["unit-test"]})
    assert configured is not structured
    assert isinstance(configured, Runnable)


@pytest.mark.asyncio
async def test_structured_output_parses_plain_json():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"intent": "visa", "confidence": 0.9})
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="What is KITAS?")])

    assert isinstance(result, _Sample)
    assert result.intent == "visa"
    assert result.confidence == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_structured_output_unwraps_markdown_fence():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = "Sure, here is the JSON:\n```json\n{\"intent\": \"tax\"}\n```\nLet me know."
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="What is NPWP?")])

    assert result.intent == "tax"


@pytest.mark.asyncio
async def test_structured_output_extracts_from_prose():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = 'Result: {"intent": "property", "confidence": 0.42} that is the answer.'
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="What is HGB?")])

    assert result.intent == "property"


@pytest.mark.asyncio
async def test_structured_output_raises_on_malformed_json():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    with _make_model_with_response("definitely not json at all"):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        with pytest.raises(json.JSONDecodeError):
            await structured.ainvoke([HumanMessage(content="hi")])


@pytest.mark.asyncio
async def test_structured_output_raises_validation_error_on_bad_schema():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    # Missing required `intent` field → ValidationError
    payload = json.dumps({"confidence": 0.5})
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        with pytest.raises(ValidationError):
            await structured.ainvoke([HumanMessage(content="hi")])


@pytest.mark.asyncio
async def test_structured_output_include_raw_returns_envelope():
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"intent": "company_setup", "confidence": 0.75})
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample, include_raw=True)
        envelope = await structured.ainvoke([HumanMessage(content="PT PMA?")])

    assert set(envelope.keys()) == {"raw", "parsed", "parsing_error"}
    assert envelope["parsing_error"] is None
    assert envelope["parsed"].intent == "company_setup"


@pytest.mark.asyncio
async def test_include_raw_envelope_on_malformed_json():
    """Codex review: include_raw=True must return parsing_error, not raise."""
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    with _make_model_with_response("definitely not json"):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample, include_raw=True)
        envelope = await structured.ainvoke([HumanMessage(content="hi")])

    assert envelope["parsed"] is None
    assert isinstance(envelope["parsing_error"], json.JSONDecodeError)


@pytest.mark.asyncio
async def test_include_raw_envelope_on_validation_error():
    """Codex review: include_raw=True must surface ValidationError, not raise."""
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"confidence": 0.5})  # missing required `intent`
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample, include_raw=True)
        envelope = await structured.ainvoke([HumanMessage(content="hi")])

    assert envelope["parsed"] is None
    assert isinstance(envelope["parsing_error"], ValidationError)


@pytest.mark.asyncio
async def test_structured_output_handles_nested_objects():
    """Gemini review: shallow regex fails on nested JSON. Balanced scanner passes."""
    from langchain_core.messages import HumanMessage

    class Nested(BaseModel):
        intent: str
        meta: dict

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps(
        {"intent": "company_setup", "meta": {"depth": {"level": 3, "ok": True}}},
    )
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(Nested)
        result = await structured.ainvoke([HumanMessage(content="setup PT PMA")])

    assert result.intent == "company_setup"
    assert result.meta["depth"]["level"] == 3


@pytest.mark.asyncio
async def test_structured_output_handles_braces_inside_strings():
    """Gemini review: regex `[^{}]` fails on literal `{` in string values."""
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"intent": "use {literal} braces", "confidence": 0.1})
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="hi")])

    assert result.intent == "use {literal} braces"


@pytest.mark.asyncio
async def test_structured_output_skips_top_level_array_hallucination():
    """Gemini review: top-level array is not a dict — must keep scanning."""
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    # LLM emits an array first, then a valid object. Scanner should ignore
    # the array (top-level non-dict) and validate the object instead.
    payload = (
        'Examples: [1, 2, 3]\n'
        'Final answer: {"intent": "visa", "confidence": 0.8}'
    )
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="KITAS?")])

    assert result.intent == "visa"


@pytest.mark.asyncio
async def test_structured_output_picks_valid_candidate_when_schema_echoed():
    """Codex review: LLM may echo the schema then emit the answer.

    The schema-injection prompt contains a JSON object (the schema itself).
    Some LLMs copy it back before emitting the real answer. Scanner must
    iterate candidates until one validates.
    """
    from langchain_core.messages import HumanMessage

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = (
        '{"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}\n'
        'Here is the answer:\n'
        '{"intent": "tax", "confidence": 0.7}'
    )
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke([HumanMessage(content="NPWP?")])

    assert result.intent == "tax"


@pytest.mark.asyncio
async def test_structured_output_accepts_plain_string_input():
    """Pass-2 review (Codex + Gemini, 2/2): LCEL composition can pass a bare
    string to invoke. Previous list-only signature would unpack it into
    individual characters and crash."""
    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"intent": "visa", "confidence": 0.5})
    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke("Apa itu KITAS?")

    assert isinstance(result, _Sample)
    assert result.intent == "visa"


@pytest.mark.asyncio
async def test_structured_output_accepts_prompt_value_input():
    """Pass-2 review: `prompt | structured` LCEL pipeline yields a
    ChatPromptValue, not a list. Must call `.to_messages()`."""
    from langchain_core.prompts import ChatPromptTemplate

    from backend.llm.claude_oauth_langchain import build_claude_oauth_chat_model

    payload = json.dumps({"intent": "tax", "confidence": 0.6})
    prompt = ChatPromptTemplate.from_messages(
        [("system", "You are an expert."), ("human", "{question}")],
    )
    prompt_value = prompt.invoke({"question": "What is NPWP?"})

    with _make_model_with_response(payload):
        model = build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)
        result = await structured.ainvoke(prompt_value)

    assert result.intent == "tax"


@pytest.mark.asyncio
async def test_system_message_is_prepended_or_merged():
    """Gemini review: SystemMessage must be first, not appended at the end."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.llm import claude_oauth_langchain as mod

    captured: list[Any] = []

    async def fake_complete_async(prompt: str, **_: Any) -> Any:
        captured.append(prompt)
        return type("R", (), {"text": json.dumps({"intent": "visa"})})()

    from unittest.mock import patch

    with patch.object(mod, "complete_async", side_effect=fake_complete_async):
        model = mod.build_claude_oauth_chat_model()
        structured = model.with_structured_output(_Sample)

        # Case A: caller did not supply a SystemMessage — schema goes first.
        await structured.ainvoke([HumanMessage(content="USER A")])
        prompt_a = captured[-1]
        head_a = prompt_a.splitlines()[0]
        assert head_a == "[system]"

        # Case B: caller supplied their own SystemMessage — schema is merged
        # into it, not appended after the user message.
        await structured.ainvoke(
            [SystemMessage(content="ROLE"), HumanMessage(content="USER B")],
        )
        prompt_b = captured[-1]
        # First section should be the merged system content.
        assert prompt_b.startswith("[system]\nROLE")
        # The schema instruction should come BEFORE the user message.
        schema_idx = prompt_b.find("JSON object that conforms")
        user_idx = prompt_b.find("USER B")
        assert 0 < schema_idx < user_idx
