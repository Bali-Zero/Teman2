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
from typing import Any

logger = logging.getLogger(__name__)

COMPLEX_QUERY_INTENTS: frozenset[str] = frozenset(
    {"business_complex", "business_strategic", "devai_code"},
)

_VECTOR_SEARCH_MIN_CONTENT_LEN = 10
_EARLY_EXIT_MIN_TOOL_RESULT_LEN = 500


def parse_tool_calls_from_response(
    response_obj: Any,
    text_response: str,
) -> tuple[list[Any], str]:
    """Parse tool calls from a model response (native first, regex fallback).

    Returns ``(tool_calls, mode)`` where ``mode`` is one of:
      - ``"native"`` — at least one valid call found via
        ``response_obj.candidates[*].content.parts``;
      - ``"regex"`` — native yielded nothing, fallback parsed a valid
        call from ``text_response``;
      - ``"none"`` — neither path produced a valid call (empty list).

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
