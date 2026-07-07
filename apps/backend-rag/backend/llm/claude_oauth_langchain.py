"""LangChain BaseChatModel backed by ``claude -p`` (Max OAuth subprocess).

Lets LangGraph/LangChain code paths use Claude without importing
``langchain_anthropic`` (which requires ``ANTHROPIC_API_KEY``).

Minimal on purpose:
- no streaming (``_astream`` is unimplemented),
- no native tool-use / function-calling (the CLI has no built-in channel
  for it). Structured output is emulated via prompt-engineered JSON +
  Pydantic validation locally — see :meth:`with_structured_output`.
- flattens the entire conversation into a single prompt before handing off
  to :func:`backend.llm.claude_oauth_client.complete_async`.

If any of those limitations bite a consumer, we fix that consumer — we do
NOT bring back the SDK.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

from backend.llm.claude_oauth_client import (
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

logger = logging.getLogger(__name__)


_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)


def _iter_balanced_json_objects(text: str) -> Iterator[str]:
    """Yield every top-level JSON object substring in ``text``, in order.

    String-aware balanced-brace scanner: tracks `"`-quoted segments and
    backslash escapes so that braces inside JSON string values do NOT
    terminate the object early. Handles arbitrary nesting depth.

    Used for prompt-engineered structured output: the LLM may echo the
    schema or an example object before the answer, so callers should
    iterate and validate each candidate against the target Pydantic
    schema until one fits (Codex review feedback).
    """
    depth = 0
    in_string = False
    escape = False
    start = -1
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
            continue
        if ch == "}":
            if depth == 0:
                continue  # stray closing brace, ignore
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start : i + 1]
                start = -1


def _candidate_json_payloads(text: str) -> list[str]:
    """Return ordered candidate JSON-object substrings from ``text``.

    Order:
    1. Markdown-fenced ```json … ``` block (LLMs often pick this when
       instructed to wrap the answer).
    2. All top-level balanced objects in document order, parsed
       string-aware (handles nested objects + braces inside strings).
    3. The verbatim input as a last resort, so an empty candidate list
       still produces a meaningful ``json.JSONDecodeError`` upstream.
    """
    candidates: list[str] = []
    for fence in _FENCE_RE.finditer(text):
        candidates.append(fence.group(1))
    candidates.extend(_iter_balanced_json_objects(text))
    candidates.append(text)
    seen: set[str] = set()
    deduped: list[str] = []
    for cand in candidates:
        if cand not in seen:
            seen.add(cand)
            deduped.append(cand)
    return deduped


def _import_langchain_core() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Lazy-import LangChain Core so test collection doesn't require it."""
    from langchain_core.callbacks.manager import (
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
    )
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    return (
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
        BaseChatModel,
        AIMessage,
        BaseMessage,
        (ChatGeneration, ChatResult),
    )


def _flatten_messages(messages: list[Any]) -> str:
    """Fold a LangChain message list into a single prompt string.

    The CLI takes one prompt — we preserve role tags as plain-text
    prefixes so the model can still read the conversation structure.
    """
    lines: list[str] = []
    for msg in messages:
        role = getattr(msg, "type", None) or getattr(msg, "role", "user")
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            # content blocks (e.g. multimodal) → take text parts only
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(t for t in text_parts if t)
        lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines)


def _message_from_response(resp: Any) -> Any:
    """Build an ``AIMessage`` from a ``ClaudeOAuthResponse``.

    When the response carries a native ``structured`` dict (the CLI parsed a
    ``--json-schema`` envelope), stash it under ``additional_kwargs["structured"]``
    so the structured-output Runnable can validate it directly instead of
    re-scanning the prose ``content`` (review D2: ``content`` is the human-prose
    ``result``, NOT the answer). On the plain text path ``structured`` is None
    and ``additional_kwargs`` stays empty — byte-compatible with the old behavior.
    """
    from langchain_core.messages import AIMessage

    structured = getattr(resp, "structured", None)
    additional_kwargs = {"structured": structured} if structured is not None else {}
    return AIMessage(content=resp.text, additional_kwargs=additional_kwargs)


def build_claude_oauth_chat_model(
    model: str = "claude-sonnet-4-6",
    timeout_s: int = 120,
) -> Any:
    """Return a ``BaseChatModel`` instance that talks to Claude via OAuth.

    Built lazily (inside the function) so callers that don't use LangChain
    never pay the import cost. The returned object is fully compatible
    with ``LLMCompatibility``-style LangGraph nodes that expect
    ``ainvoke(messages) -> AIMessage``.
    """
    (
        _AsyncCbMgr,
        _CbMgr,
        BaseChatModel,
        _AIMessage,
        _BaseMessage,
        (ChatGeneration, ChatResult),
    ) = _import_langchain_core()

    class ClaudeOAuthChatModel(BaseChatModel):  # type: ignore[misc, valid-type]
        """LangChain chat wrapper around :mod:`claude_oauth_client`."""

        model_name: str = model
        request_timeout_s: int = timeout_s

        @property
        def _llm_type(self) -> str:
            return "claude-oauth-subprocess"

        def _generate(
            self,
            messages: list[Any],
            stop: list[str] | None = None,
            run_manager: Any | None = None,
            **kwargs: Any,
        ) -> Any:
            # LangGraph in our codebase always uses the async path, but
            # keep a sync fallback that just forwards to asyncio.run.
            import asyncio

            del stop, run_manager
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                raise RuntimeError(
                    "ClaudeOAuthChatModel._generate called inside a running "
                    "event loop; use _agenerate / ainvoke instead",
                )
            prompt = _flatten_messages(messages)
            resp = asyncio.run(
                complete_async(
                    prompt,
                    model=self.model_name,
                    timeout_s=self.request_timeout_s,
                    json_schema=kwargs.get("json_schema"),
                ),
            )
            gen = ChatGeneration(message=_message_from_response(resp))
            return ChatResult(generations=[gen])

        async def _agenerate(
            self,
            messages: list[Any],
            stop: list[str] | None = None,
            run_manager: Any | None = None,
            **kwargs: Any,
        ) -> Any:
            del stop, run_manager
            prompt = _flatten_messages(messages)
            try:
                resp = await complete_async(
                    prompt,
                    model=self.model_name,
                    timeout_s=self.request_timeout_s,
                    json_schema=kwargs.get("json_schema"),
                )
            except (ClaudeOAuthError, ClaudeOAuthNotAvailable):
                raise
            gen = ChatGeneration(message=_message_from_response(resp))
            return ChatResult(generations=[gen])

        def with_structured_output(  # type: ignore[override]
            self,
            schema: Any,
            *,
            include_raw: bool = False,
            method: str | None = None,
            **_: Any,
        ) -> Any:
            """Emulate structured output by prompt-engineered JSON + Pydantic.

            The base :class:`BaseChatModel` implementation requires native
            tool-calling, which the ``claude -p`` subprocess does not expose.
            Instead, we prepend a SystemMessage with the JSON schema, ask
            for a JSON-only answer, parse the response (string-aware
            balanced-brace scanner, multi-candidate), validate against
            ``schema``.

            ``include_raw`` matches the LangChain envelope contract:
            on success → ``{"raw": ..., "parsed": <model>, "parsing_error": None}``,
            on failure → ``{"raw": ..., "parsed": None, "parsing_error": exc}``.
            Without ``include_raw`` failures propagate as ``json.JSONDecodeError``
            or ``pydantic.ValidationError`` (the caller in
            ``understand_query_node`` already handles both).

            ``method`` is accepted for LangChain API parity. Only the
            prompt-engineered JSON strategy is supported, so the value is
            stored on the wrapper for transparency but not branched on.
            """
            return _ClaudeStructuredRunnable(
                self,
                schema,
                include_raw=include_raw,
                method=method or "json_mode",
            )

    return ClaudeOAuthChatModel()


def _schema_to_json_schema(schema: Any) -> dict[str, Any] | None:
    """Return the JSON-Schema dict for ``schema``, or None if not derivable.

    Used for the NATIVE ``--json-schema`` path: a Pydantic model yields a real
    JSON Schema; a bare dict is assumed already-a-schema; anything else (a raw
    string description) has no schema and returns None so the caller falls back
    to the prompt-engineered text path.
    """
    if isinstance(schema, dict):
        return schema
    try:
        return schema.model_json_schema()  # Pydantic v2
    except AttributeError:
        try:
            return schema.schema()  # Pydantic v1
        except AttributeError:
            return None


def _build_schema_hint(schema: Any) -> str:
    """Render a JSON-schema hint suitable for prompt injection."""
    json_schema = _schema_to_json_schema(schema)
    if json_schema is None:
        json_schema = {"description": str(schema)}
    return json.dumps(json_schema, ensure_ascii=False, sort_keys=True)


def _validate_against_schema(raw_text: str, schema: Any) -> Any:
    """Try every candidate JSON object until one validates.

    Raises ``json.JSONDecodeError`` if no candidate decodes at all, or
    ``pydantic.ValidationError`` if a candidate decoded but none validated
    (the last validation error is re-raised so callers see a real schema
    diagnostic, not a stale parse error).
    """
    last_validation_error: Exception | None = None
    last_decode_error: Exception | None = None
    decoded_any = False

    for candidate in _candidate_json_payloads(raw_text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_decode_error = exc
            continue
        decoded_any = True
        if not isinstance(parsed, dict):
            # LLMs can hallucinate top-level arrays/primitives. Skip and
            # keep scanning for a real object.
            continue
        try:
            return _model_validate(schema, parsed)
        except Exception as exc:  # ValidationError or v1 equivalent
            last_validation_error = exc
            continue

    if not decoded_any and last_decode_error is not None:
        raise last_decode_error
    if last_validation_error is not None:
        raise last_validation_error
    # No candidate, no error: synthesise a JSONDecodeError so callers can
    # rely on a single failure mode contract.
    raise json.JSONDecodeError("no JSON object found in response", raw_text or "", 0)


def _model_validate(schema: Any, parsed: dict) -> Any:
    """Pydantic v2 first, fall back to v1. Only AttributeError is caught."""
    try:
        return schema.model_validate(parsed)  # Pydantic v2
    except AttributeError:
        return schema.parse_obj(parsed)  # Pydantic v1


def _normalize_to_messages(input_value: Any) -> list[Any]:
    """Coerce a LangChain Runnable ``input`` into a list of BaseMessage.

    Accepts the three shapes LCEL composition produces: a plain string
    (``model.invoke("hello")``), a ``PromptValue`` (``prompt | structured``
    composition), or an existing ``list[BaseMessage]``. Pass-2 cross-LLM
    review (Codex + Gemini, 2/2) flagged that the previous list-only
    signature crashed when handed a string (``*messages`` would unpack it
    into individual characters) or a PromptValue (no ``__getitem__``).
    """
    from langchain_core.messages import HumanMessage
    from langchain_core.prompt_values import PromptValue

    if isinstance(input_value, str):
        return [HumanMessage(content=input_value)]
    if isinstance(input_value, PromptValue):
        return list(input_value.to_messages())
    if isinstance(input_value, list):
        return list(input_value)
    # Single message or unknown — wrap in a list so downstream code is
    # uniform. Genuinely invalid inputs will surface from the underlying
    # `_agenerate` validation, which is the right layer for that.
    return [input_value]


def _augment_messages_with_schema(input_value: Any, schema_hint: str) -> list[Any]:
    """Prepend / merge the schema instruction as a SystemMessage.

    LLM endpoints expect SystemMessage as the first message (Gemini review
    feedback). If the caller already supplied one, we merge by appending
    the schema to its content; otherwise we prepend a fresh SystemMessage.

    Accepts any LangChain Runnable input (string, PromptValue, list of
    messages) — see :func:`_normalize_to_messages`.
    """
    from langchain_core.messages import SystemMessage

    messages = _normalize_to_messages(input_value)
    instruction = (
        "Respond with a single JSON object that conforms to this JSON "
        "schema. Do not include prose or markdown fences:\n"
        f"{schema_hint}"
    )

    if messages and isinstance(messages[0], SystemMessage):
        head = messages[0]
        merged_content = f"{head.content}\n\n{instruction}"
        return [SystemMessage(content=merged_content), *messages[1:]]
    return [SystemMessage(content=instruction), *messages]


def _build_runnable_class() -> type:
    """Build ``_ClaudeStructuredRunnable`` lazily so import has no langchain dep."""
    from langchain_core.runnables import Runnable

    class _ClaudeStructuredRunnable(Runnable):  # type: ignore[misc, valid-type]
        """LangChain Runnable that wraps the Claude OAuth chat model.

        Inherits from :class:`Runnable` so downstream consumers
        (``with_config``, ``with_retry``, pipe composition, ``batch``)
        work without surprises (Codex review feedback).
        """

        def __init__(
            self,
            model: Any,
            schema: Any,
            *,
            include_raw: bool = False,
            method: str = "json_mode",
        ) -> None:
            super().__init__()
            self._model = model
            self._schema = schema
            self._include_raw = include_raw
            self._method = method
            self._schema_hint = _build_schema_hint(schema)
            # Native JSON Schema for the CLI ``--json-schema`` path. None when
            # the schema can't be rendered (raw string description) → the call
            # uses the prompt-engineered text path only.
            self._native_schema = _schema_to_json_schema(schema)

        def _validate_native(self, structured: dict) -> Any:
            """Validate a native ``structured_output`` dict against the schema.

            ``structured`` is the real answer object from the CLI envelope, so
            we feed it straight to Pydantic — NO heuristic brace-scanner (that
            scanner exists only to dig an object out of prose, review D2).
            """
            if isinstance(self._schema, dict):
                # Caller passed a bare JSON Schema (not a Pydantic model): the
                # CLI already validated against it, so return the dict as-is.
                return structured
            return _model_validate(self._schema, structured)

        def _wrap_text_result(self, raw: Any) -> Any:
            """Validate the PROSE content via the heuristic scanner (text path)."""
            content = getattr(raw, "content", str(raw))
            if self._include_raw:
                try:
                    parsed = _validate_against_schema(content, self._schema)
                    return {"raw": raw, "parsed": parsed, "parsing_error": None}
                except Exception as exc:
                    return {"raw": raw, "parsed": None, "parsing_error": exc}
            return _validate_against_schema(content, self._schema)

        def _wrap_native_result(self, raw: Any, structured: dict) -> Any:
            if self._include_raw:
                try:
                    parsed = self._validate_native(structured)
                    return {"raw": raw, "parsed": parsed, "parsing_error": None}
                except Exception as exc:
                    return {"raw": raw, "parsed": None, "parsing_error": exc}
            return self._validate_native(structured)

        def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
            # Native path: ask the CLI for --json-schema output when derivable.
            if self._native_schema is not None:
                messages = _normalize_to_messages(input)
                native = self._model.invoke(
                    messages, config=config, json_schema=self._native_schema, **kwargs
                )
                structured = getattr(native, "additional_kwargs", {}).get("structured")
                if isinstance(structured, dict):
                    return self._wrap_native_result(native, structured)
                # SEQUENTIAL fallback (review D3): the structured envelope was
                # absent (CLI lacks the flag / model declined) → re-call in plain
                # text mode with the schema prompt-injected. We NEVER feed the
                # envelope's prose ``result`` to the validator.
            messages = _augment_messages_with_schema(input, self._schema_hint)
            result = self._model.invoke(messages, config=config, **kwargs)
            return self._wrap_text_result(result)

        async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
            if self._native_schema is not None:
                messages = _normalize_to_messages(input)
                native = await self._model.ainvoke(
                    messages, config=config, json_schema=self._native_schema, **kwargs
                )
                structured = getattr(native, "additional_kwargs", {}).get("structured")
                if isinstance(structured, dict):
                    return self._wrap_native_result(native, structured)
                # SEQUENTIAL fallback (review D3) — see invoke() above.
            messages = _augment_messages_with_schema(input, self._schema_hint)
            result = await self._model.ainvoke(messages, config=config, **kwargs)
            return self._wrap_text_result(result)

    return _ClaudeStructuredRunnable


def _ClaudeStructuredRunnable(
    model: Any,
    schema: Any,
    *,
    include_raw: bool = False,
    method: str = "json_mode",
) -> Any:
    """Factory entry point used by :meth:`ClaudeOAuthChatModel.with_structured_output`.

    Defers the langchain_core import until call time so this module can be
    imported in environments where langchain is not installed (test
    collection on the worktree venv).
    """
    cls = _build_runnable_class()
    return cls(model, schema, include_raw=include_raw, method=method)
