from __future__ import annotations

from typing import Any

import pytest

from backend.services.knowledge_graph import incremental_builder as builder_module
from backend.services.knowledge_graph.incremental_builder import (
    KGIncrementalBuilder,
    run_knowledge_graph_incremental_build,
)


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]] | None = None, *, fail: bool = False) -> None:
        self.rows = rows or []
        self.fail = fail
        self.queries: list[str] = []

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("database unavailable")
        self.queries.append(query)
        return self.rows


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


@pytest.mark.asyncio
async def test_get_processed_chunk_ids_returns_empty_without_pool() -> None:
    builder = KGIncrementalBuilder(db_pool=None)

    assert await builder.get_processed_chunk_ids() == set()


@pytest.mark.asyncio
async def test_get_processed_chunk_ids_reads_distinct_ids_from_pool() -> None:
    connection = FakeConnection(
        [
            {"chunk_id": "chunk-1"},
            {"chunk_id": "chunk-2"},
            {"chunk_id": None},
            {"chunk_id": "chunk-1"},
        ],
    )
    builder = KGIncrementalBuilder(db_pool=FakePool(connection))

    result = await builder.get_processed_chunk_ids()

    assert result == {"chunk-1", "chunk-2"}
    assert "FROM kg_nodes" in connection.queries[0]
    assert "FROM kg_edges" in connection.queries[0]


@pytest.mark.asyncio
async def test_get_processed_chunk_ids_returns_empty_on_database_error() -> None:
    builder = KGIncrementalBuilder(db_pool=FakePool(FakeConnection(fail=True)))

    assert await builder.get_processed_chunk_ids() == set()


@pytest.mark.asyncio
async def test_run_incremental_extraction_skips_when_database_pool_missing() -> None:
    builder = KGIncrementalBuilder(db_pool=None)

    result = await builder.run_incremental_extraction()

    assert result == {"status": "skipped", "reason": "no_database"}


@pytest.mark.asyncio
async def test_run_knowledge_graph_incremental_build_delegates_to_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_pools: list[Any] = []

    async def fake_run(self: KGIncrementalBuilder) -> dict[str, Any]:
        seen_pools.append(self.db_pool)
        return {"status": "ok", "collections_processed": 1}

    monkeypatch.setattr(KGIncrementalBuilder, "run_incremental_extraction", fake_run)
    pool = object()

    result = await run_knowledge_graph_incremental_build(pool)

    assert result == {"status": "ok", "collections_processed": 1}
    assert seen_pools == [pool]


def test_get_gemini_client_returns_none_when_google_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module.settings, "google_api_key", "")
    monkeypatch.setattr(builder_module.settings, "google_ai_studio_key", "")
    monkeypatch.setattr(builder_module.settings, "google_imagen_api_key", "")
    builder = KGIncrementalBuilder(db_pool=None)

    assert builder._get_gemini_client() is None
