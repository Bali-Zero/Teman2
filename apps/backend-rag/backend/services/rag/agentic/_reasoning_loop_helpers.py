"""
Pure helpers shared by the sync and streaming ReAct loops.

Extracted from ``reasoning.py`` (refactor/split-reasoning).

The sync (``execute_react_loop``) and streaming (``execute_react_loop_stream``)
loops are intentionally distinct algorithms — sync executes tool calls in
parallel, stream one-at-a-time; stream yields events for the UI, sync
returns at the end; stream carries images, sync doesn't. Fusing them
behind a boolean flag would reduce readability.

What IS shared and worth extracting are the pure per-step decisions:
parsing the tool call from a model response, normalising vector_search
citation output, handling generate_image output, the early-exit
predicate on vector_search results, and the "Final Answer:" prefix
extraction. Those live here.

Public API:
    - COMPLEX_QUERY_INTENTS: intents that must NOT trigger vector-search
      early exit (they may need the KG tool).
    - parse_tool_calls_from_response: native function-call first, regex
      fallback. Returns the full list (sync uses all, stream uses [0]).
    - handle_vector_search_sources: mutate ``state.sources`` in place
      from the JSON result and, when the content is substantial, replace
      ``tool_result`` with the extracted content. Returns the new
      tool_result and the count of newly collected sources.
    - handle_generate_image_result: mutate ``state.generated_images`` in
      place and return the image_url (if any) so the caller can yield
      it on the streaming path.
    - should_early_exit_on_vector_search: the shared early-exit
      predicate for vector_search (len>500, no "No relevant documents",
      intent not complex).
    - extract_final_answer_text: split on "Final Answer:" if present,
      else return the text unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

COMPLEX_QUERY_INTENTS: frozenset[str] = frozenset(
    {"business_complex", "business_strategic", "devai_code"},
)

_VECTOR_SEARCH_MIN_CONTENT_LEN = 10
_EARLY_EXIT_MIN_TOOL_RESULT_LEN = 500

# OpenRouter occasionally wraps a tool-call payload in nested ```json ... ```
# fences (```json\n```json\n{...}\n```\n```). The regex matches one fenced
# block whose body is itself another fenced block, and the substitution keeps
# only the inner body so subsequent passes can operate on the raw JSON. We
# iterate until the string stabilises because wrapping can be deeper than 2.
_NESTED_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?```(?:json)?\s*\n?(.*?)\n?```\s*\n?```",
    re.DOTALL,
)
# Single-fence unwrapper, applied after nested fences have been flattened so
# degraded extraction sees plain text around the JSON object.
_SINGLE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_TOOL_NAME_MARKER = '"tool_name"'


def _strip_nested_fences(text: str) -> str:
    """Collapse nested ```json``` fence wrappers until the string stabilises.

    OpenRouter's non-OpenAI-compatible endpoints sometimes double-wrap their
    payload. A single `re.sub` call only peels one layer, so we loop until
    the substitution is a no-op (or a small cap is reached as a belt-and-
    braces bound against pathological inputs).
    """
    previous = None
    current = text
    # Bound iterations: deepest observed nesting is 2, cap at 8 to be safe.
    for _ in range(8):
        if current == previous:
            break
        previous = current
        current = _NESTED_FENCE_RE.sub(r"\1", current)
    return _SINGLE_FENCE_RE.sub(r"\1", current)


def _find_first_balanced_tool_object(text: str) -> str | None:
    """Return the first ``{...}`` substring containing ``"tool_name"``.

    Scans character-by-character tracking brace depth while respecting
    JSON string quoting (so ``{"x": "}{"}`` counts as one balanced object,
    not three). Returns the smallest well-formed balanced slice starting
    at a ``{`` that, once closed at depth 0, contains the literal
    ``"tool_name"`` marker. Returns ``None`` if no such slice exists.

    Intentionally non-greedy: we only want the first viable object so the
    degraded path does not over-match on surrounding prose.
    """
    start: int | None = None
    depth = 0
    in_string = False
    escape = False

    i = 0
    length = len(text)
    while i < length:
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            i += 1
            continue

        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = text[start : i + 1]
                    if _TOOL_NAME_MARKER in candidate:
                        return candidate
                    # Reset and keep scanning for the next top-level object.
                    start = None
        i += 1

    return None


def _tool_call_from_json(isolated_json: str) -> Any:
    """Build a ``ToolCall`` from a raw OpenRouter-style JSON slice.

    Accepts the output of :func:`_find_first_balanced_tool_object` — a
    single balanced object that contains ``"tool_name"``. Returns a
    :class:`ToolCall` populated from the JSON (mapping ``tool_input`` /
    ``arguments`` / ``parameters`` to the dataclass's ``arguments`` field),
    or ``None`` if the slice is not valid JSON, is missing ``tool_name``,
    or the arguments are not a mapping.

    ``ToolCall`` is imported lazily to avoid a module-load cycle with
    ``tool_executor`` and to keep this helper file cheap to import.
    """
    try:
        parsed = json.loads(isolated_json)
    except json.JSONDecodeError as exc:
        logger.debug("regex_degraded JSON decode failed: %s", exc)
        return None

    if not isinstance(parsed, dict):
        return None

    tool_name = parsed.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return None

    # OpenRouter callers use "tool_input"; some clients use "arguments" or
    # "parameters". Accept any of them, default to an empty dict so a call
    # with no args is still usable downstream.
    arguments = (
        parsed.get("tool_input")
        or parsed.get("arguments")
        or parsed.get("parameters")
        or {}
    )
    if not isinstance(arguments, dict):
        return None

    from backend.services.tools.definitions import ToolCall

    return ToolCall(tool_name=tool_name, arguments=arguments)


def parse_tool_calls_from_response(
    response_obj: Any,
    text_response: str,
) -> tuple[list[Any], str]:
    """Parse tool calls from a model response (native → regex → regex_degraded).

    Returns ``(tool_calls, mode)`` where ``mode`` is one of:
      - ``"native"`` — at least one valid call found via
        ``response_obj.candidates[*].content.parts``;
      - ``"regex"`` — native yielded nothing, fallback parsed a valid
        call from ``text_response``;
      - ``"regex_degraded"`` — native and regex both failed; a third
        pass unwraps nested ```json``` fences (OpenRouter double-wrap)
        and extracts the first brace-balanced JSON object containing
        ``"tool_name"``, then retries ``parse_tool_call`` on that slice.
        Activates only when the standard regex fallback produced an
        invalid call;
      - ``"none"`` — none of the paths produced a valid call (empty list).

    The sync loop executes all returned calls in parallel; the streaming
    loop uses only the first element.

    ``parse_tool_call`` and ``is_valid_tool_call`` are resolved via the
    reasoning module at call time so tests that patch
    ``backend.services.rag.agentic.reasoning.parse_tool_call`` continue
    to intercept the call.
    """
    from backend.services.rag.agentic import reasoning as _reasoning_module

    parse_tool_call = _reasoning_module.parse_tool_call
    is_valid_tool_call = _reasoning_module.is_valid_tool_call

    tool_calls: list[Any] = []

    if hasattr(response_obj, "candidates") and response_obj.candidates:
        for candidate in response_obj.candidates:
            if (
                hasattr(candidate, "content")
                and candidate.content is not None
                and hasattr(candidate.content, "parts")
                and candidate.content.parts
            ):
                for part in candidate.content.parts:
                    tc = parse_tool_call(part, use_native=True)
                    if tc and is_valid_tool_call(tc):
                        tool_calls.append(tc)
                if tool_calls:
                    return tool_calls, "native"

    tc = parse_tool_call(text_response, use_native=False)
    if is_valid_tool_call(tc):
        return [tc], "regex"

    # regex_degraded: only triggered when native yielded nothing AND the
    # plain regex fallback produced an invalid tool_call.
    #
    # The standard parser (``parse_tool_call_regex`` in ``tool_executor.py``)
    # only understands ``ACTION: tool(args)`` text; it does not recognise
    # OpenRouter's ``{"tool_name": ..., "tool_input": ...}`` JSON shape. So
    # once we've isolated a brace-balanced JSON object we must build the
    # ``ToolCall`` directly rather than delegating back to ``parse_tool_call``
    # (which would return ``None`` and collapse the degraded path to ``"none"``).
    unwrapped = _strip_nested_fences(text_response)
    isolated = _find_first_balanced_tool_object(unwrapped)
    if isolated is not None:
        tc_degraded = _tool_call_from_json(isolated)
        if is_valid_tool_call(tc_degraded):
            logger.debug(
                "parse_tool_calls_from_response: recovered via regex_degraded (len=%d)",
                len(isolated),
            )
            return [tc_degraded], "regex_degraded"

    return [], "none"


def handle_vector_search_sources(
    state: Any,
    tool_result: str,
    *,
    log_prefix: str = "Agent",
) -> tuple[str, int, bool]:
    """Normalise a vector_search tool_result and collect its sources.

    Parses ``tool_result`` as JSON. When it contains a ``sources`` list:
      - extends ``state.sources`` with the new sources (creates the
        attribute if missing);
      - if ``content`` has more than 10 non-whitespace chars, replaces
        ``tool_result`` with ``content`` so downstream steps see the
        distilled text rather than the JSON envelope;
      - otherwise keeps the original tool_result but still collects
        sources (logs a warning).

    Returns ``(new_tool_result, new_source_count, content_substantial)``.
    ``content_substantial`` is True only when content was extracted (and
    ``tool_result`` was therefore replaced). Callers can use that flag
    to emit the positive "collected N sources" log only on the happy
    path, matching the pre-extraction behaviour.
    Non-JSON results or unexpected shapes pass through unchanged,
    count = 0, content_substantial = False.
    """
    try:
        parsed = json.loads(tool_result)
    except json.JSONDecodeError as exc:
        logger.debug("Vector search JSON decode skipped: %s", exc)
        return tool_result, 0, False
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse vector_search: %s", exc)
        return tool_result, 0, False

    if not (isinstance(parsed, dict) and "sources" in parsed):
        return tool_result, 0, False

    content = parsed.get("content", "")
    new_sources = parsed.get("sources", [])

    if content and len(content.strip()) > _VECTOR_SEARCH_MIN_CONTENT_LEN:
        new_tool_result = content
        if not hasattr(state, "sources"):
            state.sources = []
        state.sources.extend(new_sources)
        return new_tool_result, len(new_sources), True

    logger.warning(
        "⚠️ [%s] Vector search empty content with %d sources",
        log_prefix,
        len(new_sources),
    )
    if new_sources:
        if not hasattr(state, "sources"):
            state.sources = []
        state.sources.extend(new_sources)
    return tool_result, len(new_sources), False


def handle_generate_image_result(
    state: Any,
    tool_result: str,
) -> dict[str, Any] | None:
    """Parse a generate_image tool_result; mutate state, return url payload.

    If the result decodes to ``{"success": True, "image_url"|"image_data": ...}``,
    appends the URL to ``state.generated_images`` (creating it on demand)
    and returns a dict the streaming loop can yield::

        {"url": <str>, "service": <str>, "prompt": <str>}

    Returns ``None`` when the JSON is malformed, ``success`` is false,
    or no URL is present — the sync loop ignores ``None``, the stream
    loop skips the yield.
    """
    try:
        parsed = json.loads(tool_result)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.debug("Image URL parse skipped: %s", exc)
        return None

    if not (isinstance(parsed, dict) and parsed.get("success")):
        return None

    image_url = parsed.get("image_url") or parsed.get("image_data")
    if not image_url:
        return None

    if not hasattr(state, "generated_images"):
        state.generated_images = []
    state.generated_images.append(image_url)

    return {
        "url": image_url,
        "service": parsed.get("service", "unknown"),
        "prompt": parsed.get("message", ""),
    }


def should_early_exit_on_vector_search(
    tool_name: str,
    tool_result: str,
    intent_type: str,
) -> bool:
    """Return True when a vector_search result is strong enough to stop.

    Triggered when the tool is ``vector_search``, the result has more
    than 500 chars, does not contain the "No relevant documents"
    sentinel, and the intent is NOT in COMPLEX_QUERY_INTENTS (those may
    still need the KG tool to produce a complete answer).
    """
    if tool_name != "vector_search":
        return False
    if len(tool_result) <= _EARLY_EXIT_MIN_TOOL_RESULT_LEN:
        return False
    if "No relevant documents" in tool_result:
        return False
    if intent_type in COMPLEX_QUERY_INTENTS:
        return False
    return True


def extract_final_answer_text(text_response: str) -> str:
    """Return the substring after the last ``Final Answer:`` marker, else the input."""
    if "Final Answer:" in text_response:
        return text_response.split("Final Answer:")[-1].strip()
    return text_response
