"""Robust JSON parsing for local LLM judges.

This module is deliberately small and dependency-free: callers provide the
model call, this wrapper retries only empty/unparseable replies and returns a
typed result instead of turning junk into a confident decision.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


DEFAULT_PARSER_FEEDBACK = (
    "Your previous reply was not valid JSON. "
    "Reply with exactly one JSON object and no surrounding text."
)


class RobustParseError(ValueError):
    """Raised when a model reply does not contain a JSON object."""


@dataclass(frozen=True)
class JudgeResult:
    """Structured result for a parsed LLM judge call."""

    ok: bool
    fallback: bool
    value: dict[str, Any]
    raw: str
    attempts: int
    error: str | None = None


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first valid JSON object from a model reply.

    The parser accepts common LLM wrappers such as markdown fences or a short
    preamble, but it still requires an actual JSON object.
    """
    if not text or not text.strip():
        raise RobustParseError("empty response")

    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    raise RobustParseError("no JSON object found")


async def robust_json_call(
    call: Callable[[str | None], Awaitable[str]],
    *,
    default_value: dict[str, Any],
    max_retries: int = 2,
    backoff_seconds: tuple[float, ...] = (0.5, 1.5),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    parser_feedback: str = DEFAULT_PARSER_FEEDBACK,
) -> JudgeResult:
    """Call an LLM until it returns one JSON object or retries are exhausted.

    Transport/runtime failures are intentionally not swallowed here. The caller
    still owns tier fallback for unavailable models; this wrapper handles only
    the "model answered, but the answer is empty or not JSON" defect.
    """
    attempts = max_retries + 1
    first_raw = ""
    last_raw = ""
    last_error: str | None = None
    feedback: str | None = None

    for attempt in range(1, attempts + 1):
        raw = await call(feedback)
        last_raw = raw or ""
        if attempt == 1:
            first_raw = last_raw

        try:
            return JudgeResult(
                ok=True,
                fallback=False,
                value=parse_json_object(last_raw),
                raw=last_raw,
                attempts=attempt,
            )
        except RobustParseError as exc:
            last_error = str(exc)
            if attempt >= attempts:
                break
            delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
            await sleep(delay)
            feedback = parser_feedback

    return JudgeResult(
        ok=False,
        fallback=True,
        value=dict(default_value),
        raw=first_raw or last_raw,
        attempts=attempts,
        error=last_error,
    )
