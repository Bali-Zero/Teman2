from __future__ import annotations

import numpy as np
import pytest

from backend.services.routing.golden_router_service import GoldenRouterService


class FakeGoldenAnswerService:
    def __init__(self, result: dict | None) -> None:
        self.result = result
        self.queries: list[str] = []

    async def find_similar(self, query: str) -> dict | None:
        self.queries.append(query)
        return self.result


class FakeEmbeddings:
    def __init__(self, query_embedding: list[float] | None = None) -> None:
        self.query_embedding = query_embedding or [1.0, 0.0]

    async def generate_embeddings_async(self, queries: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _query in queries]

    def generate_embeddings(self, queries: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _query in queries]

    def generate_query_embedding(self, query: str) -> list[float]:
        return self.query_embedding


class FakeConnection:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str) -> list[dict]:
        assert "FROM golden_routes" in sql
        return self.rows

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))


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
        self.closed = False

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_initialize_loads_routes_and_generates_embeddings(tmp_path, monkeypatch) -> None:
    rows = [
        {
            "route_id": "route_1",
            "canonical_query": "How do I apply for KITAS?",
            "document_ids": ["doc-1"],
            "chapter_ids": ["chapter-1"],
            "collections": ["visa_oracle"],
            "routing_hints": '{"priority": "visa"}',
        },
    ]
    service = GoldenRouterService(embeddings_generator=FakeEmbeddings())
    service.db_pool = FakePool(FakeConnection(rows))
    monkeypatch.chdir(tmp_path)

    await service.initialize()
    assert service._embeddings_task is not None
    await service._embeddings_task

    assert service.routes_cache == [
        {
            "route_id": "route_1",
            "canonical_query": "How do I apply for KITAS?",
            "document_ids": ["doc-1"],
            "chapter_ids": ["chapter-1"],
            "collections": ["visa_oracle"],
            "hints": {"priority": "visa"},
        },
    ]
    assert service.route_embeddings is not None
    assert service.route_embeddings.tolist() == [[1.0, 0.0]]


@pytest.mark.asyncio
async def test_route_uses_golden_answer_service_above_threshold() -> None:
    golden = FakeGoldenAnswerService(
        {"answer": "Use investor KITAS.", "similarity": 0.91},
    )
    service = GoldenRouterService(golden_answer_service=golden)

    result = await service.route("investor visa")

    assert result == {
        "answer": "Use investor KITAS.",
        "similarity": 0.91,
        "score": 0.91,
    }
    assert golden.queries == ["investor visa"]


@pytest.mark.asyncio
async def test_route_uses_embedding_cache_and_updates_usage() -> None:
    service = GoldenRouterService(embeddings_generator=FakeEmbeddings())
    service.routes_cache = [
        {
            "route_id": "route_1",
            "document_ids": ["doc-1"],
            "chapter_ids": [],
            "collections": ["visa_oracle"],
            "hints": {"priority": "visa"},
            "canonical_query": "investor kitas",
        },
    ]
    service.route_embeddings = np.array([[1.0, 0.0]])
    updated: list[str] = []

    async def fake_update_usage_stats(route_id: str) -> None:
        updated.append(route_id)

    service._update_usage_stats = fake_update_usage_stats

    result = await service.route("investor kitas")

    assert result == {
        "route_id": "route_1",
        "document_ids": ["doc-1"],
        "chapter_ids": [],
        "collections": ["visa_oracle"],
        "score": 1.0,
        "hints": {"priority": "visa"},
    }
    assert updated == ["route_1"]


@pytest.mark.asyncio
async def test_add_route_persists_defaults_and_reloads_cache(monkeypatch) -> None:
    connection = FakeConnection()
    service = GoldenRouterService()
    service.db_pool = FakePool(connection)
    initialized: list[bool] = []

    async def fake_initialize() -> None:
        initialized.append(True)

    monkeypatch.setattr(service, "initialize", fake_initialize)

    route_id = await service.add_route(
        canonical_query="What company license do I need?",
        document_ids=["doc-2"],
    )

    assert route_id.startswith("route_")
    assert connection.executed
    _, args = connection.executed[0]
    assert args[1:] == (
        "What company license do I need?",
        ["doc-2"],
        [],
        ["legal_unified"],
    )
    assert initialized == [True]


@pytest.mark.asyncio
async def test_close_closes_existing_pool() -> None:
    pool = FakePool(FakeConnection())
    service = GoldenRouterService()
    service.db_pool = pool

    await service.close()

    assert pool.closed is True
