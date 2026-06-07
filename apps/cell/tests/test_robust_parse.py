from __future__ import annotations

import pytest

from cell.slow.robust_parse import (
    DEFAULT_PARSER_FEEDBACK,
    JudgeResult,
    RobustParseError,
    parse_json_object,
    robust_json_call,
)


async def _no_sleep(_: float) -> None:
    return None


def test_parse_json_object_accepts_markdown_wrapped_json() -> None:
    assert parse_json_object(
        'analysis:\n```json\n{"action": "none", "confidence": 1.0}\n```',
    ) == {"action": "none", "confidence": 1.0}


def test_parse_json_object_rejects_empty_or_junk() -> None:
    with pytest.raises(RobustParseError, match="empty response"):
        parse_json_object("")
    with pytest.raises(RobustParseError, match="no JSON object"):
        parse_json_object("not json")


@pytest.mark.asyncio
async def test_robust_json_call_empty_falls_back_after_three_attempts() -> None:
    calls: list[str | None] = []

    async def call(feedback: str | None) -> str:
        calls.append(feedback)
        return ""

    result = await robust_json_call(
        call,
        default_value={"action": "none", "confidence": 0.0},
        sleep=_no_sleep,
    )

    assert isinstance(result, JudgeResult)
    assert result.ok is False
    assert result.fallback is True
    assert result.attempts == 3
    assert result.value == {"action": "none", "confidence": 0.0}
    assert calls == [None, DEFAULT_PARSER_FEEDBACK, DEFAULT_PARSER_FEEDBACK]


@pytest.mark.asyncio
async def test_robust_json_call_retries_junk_then_accepts_valid_json() -> None:
    replies = ["", '{"action": "alert_silent", "confidence": 0.4}']

    async def call(_: str | None) -> str:
        return replies.pop(0)

    result = await robust_json_call(
        call,
        default_value={"action": "none"},
        sleep=_no_sleep,
    )

    assert result.ok is True
    assert result.fallback is False
    assert result.attempts == 2
    assert result.value == {"action": "alert_silent", "confidence": 0.4}


@pytest.mark.asyncio
async def test_robust_json_call_valid_first_try_does_not_retry() -> None:
    calls = 0

    async def call(_: str | None) -> str:
        nonlocal calls
        calls += 1
        return '{"action": "none", "confidence": 1.0}'

    result = await robust_json_call(
        call,
        default_value={"action": "fallback"},
        sleep=_no_sleep,
    )

    assert result.ok is True
    assert result.attempts == 1
    assert calls == 1
