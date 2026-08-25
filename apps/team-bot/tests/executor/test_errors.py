"""Every ExecutorErrorCode value must be a legal ToolError.code — proven by
actually constructing a ToolError, not by re-deriving a copy of its regex
that could silently drift from envelope.py's own pattern."""

from __future__ import annotations

import pytest

from team_bot.executor.errors import ExecutorErrorCode
from team_bot.registry.envelope import ToolError


@pytest.mark.parametrize("code", list(ExecutorErrorCode))
def test_every_code_is_a_legal_tool_error_code(code: ExecutorErrorCode) -> None:
    # Raises pydantic.ValidationError if the pattern rejects it — no try/except
    # needed, a failure here IS the test failing, which is the point.
    err = ToolError(code=code.value, message="x", retryable=False)
    assert err.code == code.value


def test_no_duplicate_values() -> None:
    values = [c.value for c in ExecutorErrorCode]
    assert len(values) == len(set(values))
