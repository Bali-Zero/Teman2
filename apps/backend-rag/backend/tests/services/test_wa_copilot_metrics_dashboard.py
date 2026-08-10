from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from backend.services.wa_copilot.metrics_dashboard import build_eval_set


def _row(conversation_id: int, *, practice_id: int | None) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "client_id": conversation_id + 100,
        "client_full_name": f"Client {conversation_id}",
        "practice_id": practice_id,
        "first_customer_msg": None,
    }


class _FakeConnection:
    def __init__(self, responses: Sequence[Sequence[dict[str, Any]]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((sql, args))
        return list(self._responses.pop(0))


class _AcquireContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakePool:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self._connection)


@pytest.mark.asyncio
async def test_build_eval_set_falls_back_when_tablesample_underfills() -> None:
    connection = _FakeConnection(
        [
            [],
            [_row(1, practice_id=501)],
            [],
            [_row(2, practice_id=None), _row(3, practice_id=None)],
        ]
    )

    result = await build_eval_set(_FakePool(connection), size=3)  # type: ignore[arg-type]

    assert [row["conversation_id"] for row in result] == [1, 2, 3]
    assert len(connection.calls) == 4
    assert "TABLESAMPLE SYSTEM (1)" in connection.calls[0][0]
    assert "ORDER BY random()" in connection.calls[1][0]
    assert "TABLESAMPLE SYSTEM (1)" in connection.calls[2][0]
    assert "ORDER BY random()" in connection.calls[3][0]
    assert connection.calls[1][1] == (3, [])
    assert connection.calls[2][1] == (2, [1])
    assert connection.calls[3][1] == (2, [1])


@pytest.mark.asyncio
async def test_build_eval_set_keeps_tablesample_fast_path() -> None:
    connection = _FakeConnection([[_row(1, practice_id=501), _row(2, practice_id=502)]])

    result = await build_eval_set(_FakePool(connection), size=2)  # type: ignore[arg-type]

    assert [row["conversation_id"] for row in result] == [1, 2]
    assert len(connection.calls) == 1
    assert "TABLESAMPLE SYSTEM (1)" in connection.calls[0][0]
