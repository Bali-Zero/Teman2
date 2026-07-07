from __future__ import annotations

from typing import Any

import pytest

from backend.services.ingestion import collection_manager as manager_module
from backend.services.ingestion.collection_manager import CollectionManager


class FakeQdrantClient:
    created: list[FakeQdrantClient] = []

    def __init__(self, qdrant_url: str, collection_name: str) -> None:
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.search_calls: list[dict[str, Any]] = []
        self.upsert_calls: list[dict[str, Any]] = []
        FakeQdrantClient.created.append(self)

    async def search(
        self,
        query_embedding: list[float],
        filter: dict[str, Any] | None,
        limit: int,
    ) -> dict[str, Any]:
        self.search_calls.append(
            {
                "query_embedding": query_embedding,
                "filter": filter,
                "limit": limit,
            },
        )
        return {"documents": ["doc"], "ids": ["id-1"], "metadatas": [{}], "distances": [0.1]}

    async def upsert_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> dict[str, Any]:
        self.upsert_calls.append(
            {
                "chunks": chunks,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "ids": ids,
            },
        )
        return {"status": "ok", "count": len(chunks)}


@pytest.fixture(autouse=True)
def fake_qdrant_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeQdrantClient.created = []
    monkeypatch.setattr(manager_module, "QdrantClient", FakeQdrantClient)


def make_manager() -> CollectionManager:
    manager = CollectionManager(qdrant_url="http://qdrant.test")
    manager.collection_definitions = {
        "logical": {"priority": "high", "doc_count": 2, "alias": "physical"},
        "plain": {"priority": "low", "doc_count": 1},
    }
    return manager


def test_get_collection_lazy_loads_alias_and_initializes_lock_state() -> None:
    manager = make_manager()

    first = manager.get_collection("logical")
    second = manager.get_collection("logical")

    assert first is second
    assert len(FakeQdrantClient.created) == 1
    assert FakeQdrantClient.created[0].qdrant_url == "http://qdrant.test"
    assert FakeQdrantClient.created[0].collection_name == "physical"
    assert "logical" in manager._collection_locks
    assert "logical" in manager._collection_read_semaphores


def test_get_collection_returns_none_for_unknown_name() -> None:
    manager = make_manager()

    assert manager.get_collection("missing") is None
    assert FakeQdrantClient.created == []


def test_list_info_and_freshness_reflect_collection_definitions() -> None:
    manager = make_manager()
    manager._collection_last_updated["logical"] = 1234.5

    assert manager.list_collections() == ["logical", "plain"]
    assert manager.get_collection_info("logical") == {
        "priority": "high",
        "doc_count": 2,
        "alias": "physical",
        "actual_name": "physical",
        "last_updated": 1234.5,
    }
    assert manager.get_collection_info("missing") is None
    freshness = manager.get_collection_freshness()
    assert freshness["logical"]["last_updated"] == 1234.5
    assert freshness["plain"]["age_seconds"] is None


def test_get_all_collections_preloads_defined_clients() -> None:
    manager = make_manager()

    collections = manager.get_all_collections()

    assert set(collections) == {"logical", "plain"}
    assert [client.collection_name for client in FakeQdrantClient.created] == [
        "physical",
        "plain",
    ]


@pytest.mark.asyncio
async def test_search_with_lock_uses_initialized_read_semaphore() -> None:
    manager = make_manager()

    result = await manager.search_with_lock(
        "logical",
        query_embedding=[0.1, 0.2],
        filter={"category": "visa"},
        limit=3,
    )

    assert result["ids"] == ["id-1"]
    client = FakeQdrantClient.created[0]
    assert client.search_calls == [
        {
            "query_embedding": [0.1, 0.2],
            "filter": {"category": "visa"},
            "limit": 3,
        },
    ]


@pytest.mark.asyncio
async def test_search_with_lock_returns_empty_result_for_unknown_collection() -> None:
    manager = make_manager()

    result = await manager.search_with_lock("missing", query_embedding=[0.1])

    assert result == {"documents": [], "ids": [], "metadatas": [], "distances": []}


@pytest.mark.asyncio
async def test_ingest_with_lock_upserts_and_records_freshness() -> None:
    manager = make_manager()

    result = await manager.ingest_with_lock(
        "logical",
        documents=["doc"],
        embeddings=[[0.1, 0.2]],
        metadatas=[{"source": "test"}],
        ids=["doc-1"],
    )

    assert result == {"status": "ok", "count": 1}
    client = FakeQdrantClient.created[0]
    assert client.upsert_calls == [
        {
            "chunks": ["doc"],
            "embeddings": [[0.1, 0.2]],
            "metadatas": [{"source": "test"}],
            "ids": ["doc-1"],
        },
    ]
    assert manager._collection_last_updated["logical"] > 0


@pytest.mark.asyncio
async def test_ingest_with_lock_raises_for_unknown_collection() -> None:
    manager = make_manager()

    with pytest.raises(ValueError, match="Collection missing not found"):
        await manager.ingest_with_lock("missing", documents=[], embeddings=[])


@pytest.mark.asyncio
async def test_ingest_with_lock_times_out_when_write_lock_is_held() -> None:
    manager = make_manager()
    manager.get_collection("logical")
    lock = manager._collection_locks["logical"]
    await lock.acquire()
    manager._lock_timeout = 0.001

    try:
        with pytest.raises(RuntimeError, match="Ingestion lock timeout for logical"):
            await manager.ingest_with_lock("logical", documents=["doc"], embeddings=[[0.1]])
    finally:
        lock.release()
