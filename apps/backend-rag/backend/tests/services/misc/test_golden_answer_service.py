from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pytest

from backend.services.misc import golden_answer_service as module
from backend.services.misc.golden_answer_service import GoldenAnswerService


class FakeAcquire:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self.conn

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeConnection:
    def __init__(
        self,
        *,
        fetchrows: list[dict[str, Any] | None] | None = None,
        fetches: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self.fetchrows = fetchrows or []
        self.fetches = fetches or []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if not self.fetchrows:
            return None
        return self.fetchrows.pop(0)

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if not self.fetches:
            return []
        return self.fetches.pop(0)

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append((query, args))


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn
        self.closed = False

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)

    async def close(self) -> None:
        self.closed = True


class FakeEmbeddingModel:
    def encode(self, texts: list[str]) -> np.ndarray:
        if len(texts) == 1:
            return np.array([[1.0, 0.0]])
        return np.array([[1.0, 0.0], [0.0, 1.0]])


@pytest.mark.asyncio
async def test_connect_creates_configured_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}
    fake_pool = FakePool(FakeConnection())

    async def fake_create_pool(database_url: str, **kwargs: Any) -> FakePool:
        created["database_url"] = database_url
        created["kwargs"] = kwargs
        return fake_pool

    monkeypatch.setattr(module.asyncpg, "create_pool", fake_create_pool)

    service = GoldenAnswerService("postgresql://example/db")
    await service.connect()

    assert service.pool is fake_pool
    assert created == {
        "database_url": "postgresql://example/db",
        "kwargs": {"min_size": 5, "max_size": 20, "command_timeout": 30},
    }


@pytest.mark.asyncio
async def test_close_closes_existing_pool() -> None:
    fake_pool = FakePool(FakeConnection())
    service = GoldenAnswerService("postgresql://example/db")
    service.pool = fake_pool

    await service.close()

    assert fake_pool.closed is True


@pytest.mark.asyncio
async def test_lookup_golden_answer_returns_exact_match_and_tracks_usage() -> None:
    conn = FakeConnection(
        fetchrows=[
            {
                "cluster_id": "cluster-1",
                "canonical_question": "How to get KITAS?",
                "answer": "Use the KITAS workflow.",
                "sources": ["source-a"],
                "confidence": 0.95,
                "usage_count": 3,
            },
        ],
    )
    service = GoldenAnswerService("postgresql://example/db")
    service.pool = FakePool(conn)

    result = await service.lookup_golden_answer(" How to get KITAS? ")

    assert result == {
        "cluster_id": "cluster-1",
        "canonical_question": "How to get KITAS?",
        "answer": "Use the KITAS workflow.",
        "sources": ["source-a"],
        "confidence": 0.95,
        "match_type": "exact",
    }
    assert conn.executed
    assert conn.executed[0][1] == ("cluster-1",)


@pytest.mark.asyncio
async def test_lookup_golden_answer_falls_back_to_semantic_match() -> None:
    conn = FakeConnection(
        fetchrows=[None],
        fetches=[
            [
                {
                    "cluster_id": "semantic-1",
                    "canonical_question": "KITAS requirements",
                    "answer": "Prepare the required documents.",
                    "sources": ["kb"],
                    "confidence": 0.88,
                    "usage_count": 10,
                },
                {
                    "cluster_id": "semantic-2",
                    "canonical_question": "Company registration",
                    "answer": "Register the PMA first.",
                    "sources": [],
                    "confidence": 0.75,
                    "usage_count": 1,
                },
            ],
        ],
    )
    service = GoldenAnswerService("postgresql://example/db")
    service.pool = FakePool(conn)
    service.model = FakeEmbeddingModel()
    service.similarity_threshold = 0.80

    result = await service.lookup_golden_answer("KITAS document checklist")

    assert result is not None
    assert result["cluster_id"] == "semantic-1"
    assert result["match_type"] == "semantic"
    assert result["similarity"] == pytest.approx(1.0)
    assert conn.executed[0][1] == ("semantic-1",)


@pytest.mark.asyncio
async def test_lookup_golden_answer_returns_none_on_lookup_error() -> None:
    class BrokenConnection(FakeConnection):
        async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
            raise RuntimeError("database unavailable")

    service = GoldenAnswerService("postgresql://example/db")
    service.pool = FakePool(BrokenConnection())

    assert await service.lookup_golden_answer("anything") is None


@pytest.mark.asyncio
async def test_get_golden_answer_stats_normalizes_nulls_and_top_rows() -> None:
    conn = FakeConnection(
        fetchrows=[
            {
                "total_golden_answers": 2,
                "total_hits": None,
                "avg_confidence": None,
                "max_usage": None,
                "min_usage": None,
            },
        ],
        fetches=[
            [
                {
                    "cluster_id": "cluster-1",
                    "canonical_question": "How to get KITAS?",
                    "usage_count": 7,
                    "last_used": date(2026, 7, 5),
                },
            ],
        ],
    )
    service = GoldenAnswerService("postgresql://example/db")
    service.pool = FakePool(conn)

    stats = await service.get_golden_answer_stats()

    assert stats == {
        "total_golden_answers": 2,
        "total_hits": 0,
        "avg_confidence": 0.0,
        "max_usage": 0,
        "min_usage": 0,
        "top_10": [
            {
                "cluster_id": "cluster-1",
                "question": "How to get KITAS?",
                "usage_count": 7,
                "last_used": "2026-07-05",
            },
        ],
    }
