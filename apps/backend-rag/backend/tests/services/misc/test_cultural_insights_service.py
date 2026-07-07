from __future__ import annotations

import pytest

from backend.services.misc.cultural_insights_service import CulturalInsightsService


class _FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def generate_query_embedding(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class _FakeCollection:
    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.search_calls: list[dict] = []

    async def upsert_documents(self, **kwargs) -> None:
        self.upserts.append(kwargs)

    async def search(self, **kwargs) -> dict:
        self.search_calls.append(kwargs)
        return {
            "documents": ["Use warm greetings", "Be patient with bureaucracy"],
            "metadatas": [{"topic": "greetings"}, {"topic": "bureaucracy"}],
            "distances": [0.0, 1.0],
        }


class _FakeCollectionManager:
    def __init__(self, collection: _FakeCollection | None) -> None:
        self.collection = collection
        self.requested_names: list[str] = []

    def get_collection(self, name: str) -> _FakeCollection | None:
        self.requested_names.append(name)
        return self.collection


@pytest.mark.asyncio
async def test_add_insight_hashes_id_and_normalizes_list_metadata() -> None:
    collection = _FakeCollection()
    embedder = _FakeEmbedder()
    service = CulturalInsightsService(
        collection_manager=_FakeCollectionManager(collection),
        embedder=embedder,
    )

    ok = await service.add_insight(
        "Start with a respectful greeting.",
        {"topic": "greeting", "when_to_use": ["first_contact", "chat"]},
    )

    assert ok is True
    assert embedder.queries == ["Start with a respectful greeting."]
    upsert = collection.upserts[0]
    assert upsert["chunks"] == ["Start with a respectful greeting."]
    assert upsert["embeddings"] == [[0.1, 0.2, 0.3]]
    assert upsert["metadatas"] == [
        {"topic": "greeting", "when_to_use": "first_contact, chat"},
    ]
    assert upsert["ids"][0].startswith("cultural_greeting_")


@pytest.mark.asyncio
async def test_add_insight_returns_false_when_collection_missing() -> None:
    service = CulturalInsightsService(
        collection_manager=_FakeCollectionManager(None),
        embedder=_FakeEmbedder(),
    )

    assert await service.add_insight("content", {"topic": "missing"}) is False


@pytest.mark.asyncio
async def test_query_insights_formats_scores_and_limits_search() -> None:
    collection = _FakeCollection()
    manager = _FakeCollectionManager(collection)
    service = CulturalInsightsService(collection_manager=manager, embedder=_FakeEmbedder())

    results = await service.query_insights("hello", when_to_use="first_contact", limit=2)

    assert manager.requested_names == ["cultural_insights"]
    assert collection.search_calls == [
        {"query_embedding": [0.1, 0.2, 0.3], "filter": None, "limit": 2},
    ]
    assert results == [
        {
            "content": "Use warm greetings",
            "metadata": {"topic": "greetings"},
            "score": 1.0,
        },
        {
            "content": "Be patient with bureaucracy",
            "metadata": {"topic": "bureaucracy"},
            "score": 0.5,
        },
    ]


@pytest.mark.asyncio
async def test_get_topics_coverage_currently_returns_empty_dict() -> None:
    service = CulturalInsightsService(
        collection_manager=_FakeCollectionManager(_FakeCollection()),
        embedder=_FakeEmbedder(),
    )

    assert await service.get_topics_coverage() == {}
