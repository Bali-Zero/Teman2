from __future__ import annotations

from typing import Any

import pytest

from backend.services.ingestion.collection_warmup_service import CollectionWarmupService


class FakeCollection:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.search_calls: list[dict[str, Any]] = []

    async def search(
        self,
        query_embedding: list[float],
        filter: dict[str, Any] | None,
        limit: int,
    ) -> dict[str, Any]:
        if self.should_fail:
            raise ValueError("qdrant rejected query")
        self.search_calls.append(
            {
                "query_embedding": query_embedding,
                "filter": filter,
                "limit": limit,
            },
        )
        return {"ids": ["doc-1"]}


class FakeCollectionManager:
    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self.collections = collections
        self.requested: list[str] = []

    def get_collection(self, collection_name: str) -> FakeCollection | None:
        self.requested.append(collection_name)
        return self.collections.get(collection_name)


class FakeEmbedder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.queries: list[str] = []

    def generate_query_embedding(self, query: str) -> list[float]:
        if self.fail:
            raise ValueError("embedding unavailable")
        self.queries.append(query)
        return [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_warmup_collection_runs_lightweight_vector_search() -> None:
    collection = FakeCollection()
    manager = FakeCollectionManager({"visa_oracle": collection})
    embedder = FakeEmbedder()
    service = CollectionWarmupService(manager, embedder)

    result = await service.warmup_collection("visa_oracle")

    assert result is True
    assert embedder.queries == ["test"]
    assert collection.search_calls == [
        {
            "query_embedding": [0.1, 0.2, 0.3],
            "filter": None,
            "limit": 1,
        },
    ]


@pytest.mark.asyncio
async def test_warmup_collection_returns_false_for_missing_collection() -> None:
    manager = FakeCollectionManager({})
    embedder = FakeEmbedder()
    service = CollectionWarmupService(manager, embedder)

    assert await service.warmup_collection("missing") is False
    assert embedder.queries == []


@pytest.mark.asyncio
async def test_warmup_collection_returns_false_for_expected_query_errors() -> None:
    manager = FakeCollectionManager({"visa_oracle": FakeCollection(should_fail=True)})
    embedder = FakeEmbedder()
    service = CollectionWarmupService(manager, embedder)

    assert await service.warmup_collection("visa_oracle") is False


@pytest.mark.asyncio
async def test_warmup_all_collections_reports_success_and_order() -> None:
    collections = {
        "pricing": FakeCollection(),
        "visa": FakeCollection(),
    }
    manager = FakeCollectionManager(collections)
    embedder = FakeEmbedder()
    service = CollectionWarmupService(manager, embedder)
    service.priority_collections = ["pricing", "visa"]

    result = await service.warmup_all_collections()

    assert result["success"] is True
    assert result["collections_warmed"] == ["pricing", "visa"]
    assert result["collections_failed"] == []
    assert result["elapsed"] >= 0
    assert manager.requested == ["pricing", "visa"]
    assert embedder.queries == [
        "What is KITAS visa Indonesia pricing?",
        "test",
        "test",
    ]


@pytest.mark.asyncio
async def test_warmup_all_collections_reports_partial_failure() -> None:
    collections = {
        "pricing": FakeCollection(),
        "visa": FakeCollection(should_fail=True),
    }
    manager = FakeCollectionManager(collections)
    embedder = FakeEmbedder()
    service = CollectionWarmupService(manager, embedder)
    service.priority_collections = ["pricing", "visa", "missing"]

    result = await service.warmup_all_collections()

    assert result["success"] is False
    assert result["collections_warmed"] == ["pricing"]
    assert result["collections_failed"] == ["visa", "missing"]
    assert "error" not in result


@pytest.mark.asyncio
async def test_warmup_all_collections_reports_embedding_failure() -> None:
    manager = FakeCollectionManager({"pricing": FakeCollection()})
    embedder = FakeEmbedder(fail=True)
    service = CollectionWarmupService(manager, embedder)
    service.priority_collections = ["pricing"]

    result = await service.warmup_all_collections()

    assert result["success"] is False
    assert result["collections_warmed"] == []
    assert result["collections_failed"] == []
    assert result["error"] == "embedding unavailable"
