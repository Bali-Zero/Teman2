from typing import Any

import pytest

from backend.scripts.benchmark_kg_performance import benchmark_bfs_traversal


class _FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return []


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
async def test_benchmark_bfs_uses_valid_tablesample_alias_order() -> None:
    connection = _FakeConnection()

    result = await benchmark_bfs_traversal(_FakePool(connection))  # type: ignore[arg-type]

    query = " ".join(connection.calls[0][0].split())
    assert "FROM kg_edges AS e TABLESAMPLE SYSTEM (1)" in query
    assert "TABLESAMPLE SYSTEM (1) AS e" not in query
    assert connection.calls[0][1] == (10,)
    assert result["n"] == 0
