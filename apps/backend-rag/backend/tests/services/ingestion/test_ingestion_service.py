from __future__ import annotations

from backend.app.models import TierLevel
from backend.services.ingestion import ingestion_service as ingestion_module
from backend.services.ingestion import legal_ingestion_service as legal_module


class FakeChunker:
    def semantic_chunk(
        self,
        text: str,
        metadata: dict[str, object],
    ) -> list[dict[str, object]]:
        assert text == "full parsed text"
        assert metadata["status_vigensi"] == "berlaku"
        assert metadata["wilayah"] == "Bali"
        return [
            {"text": "chunk one", "chunk_index": 0, "total_chunks": 2},
            {"text": "chunk two", "chunk_index": 1, "total_chunks": 2},
        ]


class FakeEmbedder:
    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["chunk one", "chunk two"]
        return [[0.1], [0.2]]


class FakeVectorDB:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def upsert_documents(
        self,
        *,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> None:
        self.calls.append(
            {"chunks": chunks, "embeddings": embeddings, "metadatas": metadatas}
        )


class FakeClassifier:
    def classify_book_tier(self, title: str, author: str, sample: str) -> TierLevel:
        assert title == "Detected Title"
        assert author == "Detected Author"
        assert sample == "full parsed text"
        return TierLevel.C

    def get_min_access_level(self, tier: TierLevel) -> int:
        assert tier is TierLevel.C
        return 2


def build_service() -> ingestion_module.IngestionService:
    service = ingestion_module.IngestionService.__new__(ingestion_module.IngestionService)
    service.chunker = FakeChunker()
    service.embedder = FakeEmbedder()
    service.vector_db = FakeVectorDB()
    service.classifier = FakeClassifier()
    return service


async def test_ingest_book_runs_standard_pipeline(monkeypatch) -> None:
    service = build_service()
    monkeypatch.setattr(service, "_is_legal_document", lambda _file_path: False)
    monkeypatch.setattr(
        ingestion_module,
        "get_document_info",
        lambda _file_path: {
            "title": "Detected Title",
            "author": "Detected Author",
            "status": "berlaku",
            "region": "Bali",
        },
    )
    monkeypatch.setattr(
        ingestion_module,
        "auto_detect_and_parse",
        lambda _file_path: "full parsed text",
    )

    result = await service.ingest_book("/tmp/book.pdf", language="id")

    assert result == {
        "success": True,
        "book_title": "Detected Title",
        "book_author": "Detected Author",
        "tier": "C",
        "chunks_created": 2,
        "message": "Successfully ingested Detected Title",
        "error": None,
    }
    assert service.vector_db.calls[0]["chunks"] == ["chunk one", "chunk two"]
    assert service.vector_db.calls[0]["metadatas"][0]["status_vigensi"] == "berlaku"
    assert service.vector_db.calls[0]["metadatas"][0]["wilayah"] == "Bali"


async def test_ingest_book_routes_legal_documents(monkeypatch) -> None:
    class FakeLegalIngestionService:
        async def ingest_legal_document(self, **kwargs):
            return {"success": True, "routed": kwargs}

    service = build_service()
    monkeypatch.setattr(service, "_is_legal_document", lambda _file_path: True)
    monkeypatch.setattr(
        legal_module,
        "LegalIngestionService",
        FakeLegalIngestionService,
    )

    result = await service.ingest_book("/tmp/legal.pdf", title="Legal Title")

    assert result == {
        "success": True,
        "routed": {
            "file_path": "/tmp/legal.pdf",
            "title": "Legal Title",
            "tier_override": None,
        },
    }


def test_is_legal_document_returns_false_when_parsing_fails(monkeypatch) -> None:
    service = ingestion_module.IngestionService.__new__(ingestion_module.IngestionService)

    def raise_parse_error(_file_path: str) -> str:
        raise RuntimeError("cannot parse")

    monkeypatch.setattr(ingestion_module, "auto_detect_and_parse", raise_parse_error)

    assert service._is_legal_document("/tmp/bad.pdf") is False
