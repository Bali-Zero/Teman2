import pytest

from backend.services.search.search_service import SearchService, _uses_named_vectors


class FakeConflictResolver:
    def get_stats(self) -> dict:
        return {
            "conflicts_detected": 4,
            "conflicts_resolved": 3,
            "timestamp_resolutions": 2,
        }


class FakeEmbedder:
    async def generate_query_embedding(self, query: str) -> list[float]:
        self.query = query
        return [0.1, 0.2, 0.3]


class FakeVectorDB:
    def __init__(self) -> None:
        self.search_calls: list[dict] = []

    async def search(
        self,
        query_embedding: list[float],
        filter: dict | None,
        limit: int,
    ) -> dict:
        self.search_calls.append(
            {
                "query_embedding": query_embedding,
                "filter": filter,
                "limit": limit,
            }
        )
        return {
            "ids": ["doc-1"],
            "documents": ["Investor KITAS overview"],
            "distances": [0.25],
            "metadatas": [{"kind": "visa"}],
        }


class FakeCollectionManager:
    def __init__(self, vector_db: FakeVectorDB | None) -> None:
        self.vector_db = vector_db
        self.requested_collections: list[str] = []

    def get_collection(self, collection_name: str) -> FakeVectorDB | None:
        self.requested_collections.append(collection_name)
        return self.vector_db


def test_uses_named_vectors_for_known_and_hybrid_collections() -> None:
    assert _uses_named_vectors("legal_unified") is True
    assert _uses_named_vectors("custom_hybrid") is True
    assert _uses_named_vectors("zantara_books") is False


def test_get_conflict_stats_merges_resolver_metrics_and_rates() -> None:
    service = SearchService.__new__(SearchService)
    service.conflict_resolver = FakeConflictResolver()
    service.conflict_stats = {
        "total_multi_collection_searches": 8,
        "conflicts_detected": 0,
        "conflicts_resolved": 0,
        "timestamp_resolutions": 0,
    }

    stats = service.get_conflict_stats()

    assert stats["total_multi_collection_searches"] == 8
    assert stats["conflicts_detected"] == 4
    assert stats["conflicts_resolved"] == 3
    assert stats["timestamp_resolutions"] == 2
    assert stats["conflict_rate"] == "50.0%"
    assert stats["resolution_rate"] == "75.0%"


def test_get_conflict_stats_handles_zero_denominators() -> None:
    service = SearchService.__new__(SearchService)
    service.conflict_resolver = FakeConflictResolver()
    service.conflict_stats = {
        "total_multi_collection_searches": 0,
        "conflicts_detected": 0,
        "conflicts_resolved": 0,
        "timestamp_resolutions": 0,
    }

    stats = service.get_conflict_stats()

    assert stats["conflict_rate"] == "0.0%"
    assert stats["resolution_rate"] == "75.0%"


@pytest.mark.asyncio
async def test_search_collection_uses_existing_collection_and_formats_results() -> None:
    vector_db = FakeVectorDB()
    service = SearchService.__new__(SearchService)
    service.embedder = FakeEmbedder()
    service.collection_manager = FakeCollectionManager(vector_db)

    result = await service.search_collection(
        query="investor kitas",
        collection_name="visa_oracle",
        limit=3,
        filter={"tier": {"$in": ["S"]}},
    )

    assert service.collection_manager.requested_collections == ["visa_oracle"]
    assert vector_db.search_calls == [
        {
            "query_embedding": [0.1, 0.2, 0.3],
            "filter": {"tier": {"$in": ["S"]}},
            "limit": 3,
        }
    ]
    assert result["query"] == "investor kitas"
    assert result["collection"] == "visa_oracle"
    assert result["results"] == [
        {
            "id": "doc-1",
            "text": "Investor KITAS overview",
            "metadata": {"kind": "visa"},
            "score": 0.8,
        }
    ]
