from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.services.knowledge_graph.ontology import EntityType, RelationType
from backend.services.knowledge_graph.pipeline import KGPipeline, PipelineConfig, PipelineStats


class FakeExtractor:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: list[dict[str, Any]] = []

    async def extract(self, text: str, chunk_id: str, two_stage: bool) -> ExtractionResult:
        self.calls.append({"text": text, "chunk_id": chunk_id, "two_stage": two_stage})
        return ExtractionResult(
            chunk_id=chunk_id,
            raw_text=text,
            entities=[
                ExtractedEntity(
                    id="e1",
                    type=EntityType.KITAS,
                    name="KITAS Investor",
                    mention="KITAS Investor",
                    confidence=0.95,
                ),
                ExtractedEntity(
                    id="e2",
                    type=EntityType.DOKUMEN,
                    name="Passport",
                    mention="passport",
                    confidence=0.4,
                ),
            ],
            relations=[
                ExtractedRelation(
                    source_id="e1",
                    target_id="e2",
                    type=RelationType.REQUIRES,
                    evidence="KITAS requires passport",
                    confidence=0.9,
                ),
            ],
        )


class FakeClosePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append((query, args))


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


class FakeValidator:
    def __init__(self) -> None:
        self.result = type(
            "ValidationResult",
            (),
            {"summary": lambda _self: {"valid": 1, "invalid": 0, "total": 1}},
        )()

    def check(self, **kwargs: Any) -> bool:
        return True


@pytest.fixture(autouse=True)
def fake_gemini_extractor(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.knowledge_graph import extractor_gemini

    monkeypatch.setattr(extractor_gemini, "GeminiKGExtractor", FakeExtractor)


def make_pipeline(**overrides: Any) -> KGPipeline:
    options = {
        "use_coreference": False,
        "use_quality_filter": False,
        "min_confidence": 0.6,
        "batch_size": 2,
        "max_concurrent": 2,
    }
    options.update(overrides)
    config = PipelineConfig(**options)
    return KGPipeline(config)


def test_pipeline_stats_to_dict_includes_duration_when_complete() -> None:
    start = datetime.now(tz=timezone.utc)
    end = start + timedelta(seconds=2.5)
    stats = PipelineStats(
        chunks_processed=2,
        entities_extracted=3,
        relations_extracted=4,
        entities_persisted=1,
        relations_persisted=2,
        duplicates_merged=1,
        errors=0,
        start_time=start,
        end_time=end,
    )

    assert stats.to_dict() == {
        "chunks_processed": 2,
        "entities_extracted": 3,
        "relations_extracted": 4,
        "entities_persisted": 1,
        "relations_persisted": 2,
        "duplicates_merged": 1,
        "errors": 0,
        "duration_seconds": 2.5,
    }


@pytest.mark.asyncio
async def test_close_closes_existing_database_pool() -> None:
    pipeline = make_pipeline()
    pool = FakeClosePool()
    pipeline._db_pool = pool

    await pipeline.close()

    assert pool.closed is True
    assert pipeline._db_pool is None


@pytest.mark.asyncio
async def test_process_chunk_normalizes_ids_and_drops_relations_to_filtered_entities() -> None:
    pipeline = make_pipeline()

    result = await pipeline.process_chunk("chunk-1", "KITAS investor requires passport copy.")

    assert [entity.id for entity in result.entities] == ["kitas_kitas_investor"]
    assert result.relations == []
    assert pipeline.stats.entities_extracted == 2
    assert pipeline.stats.relations_extracted == 1
    assert set(pipeline.entity_registry) == {"kitas_kitas_investor"}


@pytest.mark.asyncio
async def test_process_chunk_returns_empty_result_and_counts_errors_on_extractor_failure() -> None:
    pipeline = make_pipeline()

    async def fail_extract(*args: Any, **kwargs: Any) -> ExtractionResult:
        raise RuntimeError("extractor failed")

    pipeline.extractor.extract = fail_extract

    result = await pipeline.process_chunk("chunk-bad", "text")

    assert result.chunk_id == "chunk-bad"
    assert result.entities == []
    assert pipeline.stats.errors == 1


@pytest.mark.asyncio
async def test_persist_results_inserts_unique_entities_and_valid_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.services.knowledge_graph import pipeline as pipeline_module

    version_bumps: list[bool] = []
    monkeypatch.setattr(pipeline_module, "SchemaValidator", FakeValidator)
    monkeypatch.setattr(pipeline_module, "increment_kg_version", lambda: version_bumps.append(True))

    pipeline = make_pipeline()
    connection = FakeConnection()
    pipeline._db_pool = FakePool(connection)
    result = ExtractionResult(
        chunk_id="chunk-1",
        entities=[
            ExtractedEntity("kitas", EntityType.KITAS, "KITAS", "KITAS"),
            ExtractedEntity("dokumen", EntityType.DOKUMEN, "Passport", "passport"),
        ],
        relations=[
            ExtractedRelation(
                "kitas",
                "dokumen",
                RelationType.REQUIRES,
                "KITAS requires passport",
            ),
            ExtractedRelation(
                "kitas",
                "dokumen",
                RelationType.REQUIRES,
                "duplicate relation",
            ),
        ],
    )

    await pipeline.persist_results([result], source_collection="visa_oracle")

    assert pipeline.stats.entities_persisted == 2
    assert pipeline.stats.relations_persisted == 1
    assert len(connection.executed) == 3
    assert version_bumps == [True]


@pytest.mark.asyncio
async def test_process_batch_filters_exceptions_and_counts_errors() -> None:
    pipeline = make_pipeline()

    async def fake_process_chunk(chunk_id: str, text: str) -> ExtractionResult:
        if text == "bad":
            raise RuntimeError("bad chunk")
        return ExtractionResult(chunk_id=chunk_id, raw_text=text)

    pipeline.process_chunk = fake_process_chunk

    results = await pipeline.process_batch([("ok", "good"), ("bad", "bad")])

    assert [result.chunk_id for result in results] == ["ok"]
    assert pipeline.stats.errors == 1


@pytest.mark.asyncio
async def test_run_batches_chunks_and_skips_persistence_when_disabled() -> None:
    pipeline = make_pipeline(batch_size=1)
    processed_batches: list[list[tuple[str, str]]] = []

    async def fake_process_batch(batch: list[tuple[str, str]]) -> list[ExtractionResult]:
        processed_batches.append(batch)
        return [ExtractionResult(chunk_id=batch[0][0], raw_text=batch[0][1])]

    pipeline.process_batch = fake_process_batch

    stats = await pipeline.run([("c1", "text 1"), ("c2", "text 2")], persist=False)

    assert stats.chunks_processed == 2
    assert stats.end_time is not None
    assert processed_batches == [[("c1", "text 1")], [("c2", "text 2")]]


@pytest.mark.asyncio
async def test_run_from_qdrant_scrolls_points_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.core import qdrant_db

    closed: list[bool] = []
    posted_payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def json(self) -> dict[str, Any]:
            return {
                "result": {
                    "points": [
                        {"id": "p1", "payload": {"text": "long legal text " * 3}},
                        {"id": "p2", "payload": {"text": "long legal text " * 3}},
                    ],
                    "next_page_offset": None,
                },
            }

    class FakeHttp:
        async def post(self, path: str, json: dict[str, Any]) -> FakeResponse:
            posted_payloads.append({"path": path, "json": json})
            return FakeResponse()

    class FakeQdrantClient:
        def __init__(self, collection_name: str) -> None:
            self.collection_name = collection_name

        async def _get_client(self) -> FakeHttp:
            return FakeHttp()

        async def get_collection_stats(self) -> dict[str, int]:
            return {"total_documents": 2}

        async def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(qdrant_db, "QdrantClient", FakeQdrantClient)
    pipeline = make_pipeline(batch_size=1)

    async def fake_process_batch(batch: list[tuple[str, str]]) -> list[ExtractionResult]:
        return [ExtractionResult(chunk_id=chunk_id, raw_text=text) for chunk_id, text in batch]

    pipeline.process_batch = fake_process_batch

    stats = await pipeline.run_from_qdrant("visa_oracle", limit=1, persist=False)

    assert stats.chunks_processed == 1
    assert posted_payloads[0]["path"] == "/collections/visa_oracle/points/scroll"
    assert closed == [True]


def test_get_stats_and_cache_stats_reflect_current_state() -> None:
    pipeline = make_pipeline()
    pipeline.stats.chunks_processed = 3
    pipeline.entity_registry["kitas"] = ExtractedEntity("kitas", EntityType.KITAS, "KITAS", "KITAS")
    pipeline.relation_registry.add("kitas_REQUIRES_doc")

    assert pipeline.get_stats()["chunks_processed"] == 3
    cache_stats = pipeline.get_cache_stats()
    assert cache_stats["entity_registry_size"] == 1
    assert cache_stats["relation_registry_size"] == 1
    assert cache_stats["coreference_cache"]["total_entities"] == 0
