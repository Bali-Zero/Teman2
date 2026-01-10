import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def _load_module(monkeypatch):
    def assess_document_quality(text):
        return {
            "text_fingerprint": f"fp:{len(text)}",
            "is_incomplete": False,
            "ocr_quality_score": 0.9,
            "needs_reextract": False,
        }

    def extract_ayat_numbers(_text):
        return [1, 2]

    def validate_ayat_sequence(numbers):
        return {
            "ayat_count_detected": len(numbers),
            "ayat_max_detected": max(numbers) if numbers else 0,
            "ayat_numbers": numbers,
            "ayat_sequence_valid": True,
            "ayat_validation_error": None,
        }

    quality_stub = types.SimpleNamespace(
        assess_document_quality=assess_document_quality,
        extract_ayat_numbers=extract_ayat_numbers,
        validate_ayat_sequence=validate_ayat_sequence,
        redis_url='redis://localhost:6379'
    )
    monkeypatch.setitem(sys.modules, "core.legal.quality_validators", quality_stub)

    settings_stub = types.SimpleNamespace(database_url="postgres://test", redis_url='redis://localhost:6379')
    monkeypatch.setitem(
        sys.modules, "app.core.config", types.SimpleNamespace(settings=settings_stub, redis_url='redis://localhost:6379')
    )

    backend_path = Path(__file__).resolve().parents[4] / "backend"
    module_name = "core.legal.hierarchical_indexer"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "core" / "legal" / "hierarchical_indexer.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _DummyEmbeddings:
    def generate_embeddings(self, texts):
        return [[0.1] for _ in texts]


class _DummyQdrant:
    def __init__(self):
        self.calls = []

    async def upsert_documents(self, chunks, embeddings, metadatas, ids):
        self.calls.append(
            {"chunks": chunks, "embeddings": embeddings, "metadatas": metadatas, "ids": ids}
        )


class _DummyParser:
    def __init__(self, structure):
        self.structure = structure

    def parse(self, _text):
        return self.structure


class _DummyChunker:
    def __init__(self, chunks):
        self.chunks = chunks

    def chunk(self, _text, metadata):
        return [{"text": c, **metadata} for c in self.chunks]


class _DummyConn:
    def __init__(self, error_on_quality=False):
        self.error_on_quality = error_on_quality
        self.executed = []

    async def execute(self, _query, *args):
        if self.error_on_quality and "text_fingerprint" in _query:
            raise RuntimeError("column does not exist")
        self.executed.append((_query.strip(), args))


class _AcquireCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPool:
    def __init__(self, conn):
        self.conn = conn
        self.closed = False

    def acquire(self):
        return _AcquireCtx(self.conn)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_index_with_bab_and_pasal(monkeypatch):
    module = _load_module(monkeypatch)
    structure = {
        "batang_tubuh": [
            {
                "number": "I",
                "title": "General",
                "text": "BAB I text",
                "pasal": [{"number": 1, "text": "Pasal 1 text"}],
            }
        ]
    }
    indexer = module.HierarchicalIndexer(
        structure_parser=_DummyParser(structure),
        qdrant_client=_DummyQdrant(),
        embeddings=_DummyEmbeddings(),
    )
    indexer._upsert_parent_documents = AsyncMock()

    result = await indexer.index_legal_document("doc", "DOC1", {"lang": "id"})

    assert result["chunks_indexed"] == 1
    assert result["parent_documents"] == 1


@pytest.mark.asyncio
async def test_index_with_pasal_list(monkeypatch):
    module = _load_module(monkeypatch)
    structure = {"pasal_list": [{"number": 1, "text": "Pasal 1 text"}]}
    indexer = module.HierarchicalIndexer(
        structure_parser=_DummyParser(structure),
        qdrant_client=_DummyQdrant(),
        embeddings=_DummyEmbeddings(),
    )
    indexer._upsert_parent_documents = AsyncMock()

    result = await indexer.index_legal_document("doc", "DOC2", {"lang": "id"})

    assert result["chunks_indexed"] == 1
    assert result["parent_documents"] == 0


@pytest.mark.asyncio
async def test_index_fallback_chunker(monkeypatch):
    module = _load_module(monkeypatch)
    structure = {}
    chunker = _DummyChunker(["a", "b"])
    qdrant = _DummyQdrant()
    indexer = module.HierarchicalIndexer(
        structure_parser=_DummyParser(structure),
        qdrant_client=qdrant,
        embeddings=_DummyEmbeddings(),
        chunker=chunker,
    )
    indexer._upsert_parent_documents = AsyncMock()

    result = await indexer.index_legal_document("doc", "DOC3", {"lang": "id"})

    assert result["chunks_indexed"] == 2
    assert qdrant.calls


def test_add_pasal_splits_long_text(monkeypatch):
    module = _load_module(monkeypatch)
    chunker = _DummyChunker(["c1", "c2"])
    indexer = module.HierarchicalIndexer(
        _DummyParser({}), _DummyQdrant(), _DummyEmbeddings(), chunker=chunker
    )
    chunks = []

    indexer._add_pasal_to_chunks(
        pasal={"number": 1, "text": "x" * 5000},
        document_id="DOC",
        bab_id="DOC_BAB_I",
        bab_title="BAB I",
        metadata={},
        chunks_to_index=chunks,
    )

    assert len(chunks) == 2
    assert chunks[0].chunk_id.endswith("_0")


def test_add_pasal_small_text(monkeypatch):
    module = _load_module(monkeypatch)
    indexer = module.HierarchicalIndexer(_DummyParser({}), _DummyQdrant(), _DummyEmbeddings())
    chunks = []

    indexer._add_pasal_to_chunks(
        pasal={"number": 1, "text": "Pasal text"},
        document_id="DOC",
        bab_id=None,
        bab_title=None,
        metadata={},
        chunks_to_index=chunks,
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["ayat_count"] == 2


@pytest.mark.asyncio
async def test_upsert_hierarchical_chunks(monkeypatch):
    module = _load_module(monkeypatch)
    qdrant = _DummyQdrant()
    indexer = module.HierarchicalIndexer(_DummyParser({}), qdrant, _DummyEmbeddings())

    chunk = module.HierarchicalChunk(
        chunk_id="DOC_Pasal_1",
        text="text",
        document_id="DOC",
        chapter_id=None,
        section_id=None,
        article_id="DOC_Pasal_1",
        hierarchy_path="DOC/Pasal_1",
        hierarchy_level=3,
        parent_chunk_ids=["DOC"],
        sibling_chunk_ids=[],
        bab_title=None,
        bab_full_text=None,
        metadata={"chunk_id": "DOC_Pasal_1"},
    )

    await indexer._upsert_hierarchical_chunks([chunk], embeddings=[[0.1]])

    assert qdrant.calls
    metadata = qdrant.calls[0]["metadatas"][0]
    assert metadata["chunk_id"] != "DOC_Pasal_1"


@pytest.mark.asyncio
async def test_upsert_parent_documents_fallback(monkeypatch):
    module = _load_module(monkeypatch)
    indexer = module.HierarchicalIndexer(_DummyParser({}), _DummyQdrant(), _DummyEmbeddings())
    conn = _DummyConn(error_on_quality=True)
    pool = _DummyPool(conn)
    indexer._get_db_pool = AsyncMock(return_value=pool)

    await indexer._upsert_parent_documents(
        [
            {
                "id": "DOC_BAB_I",
                "document_id": "DOC",
                "type": "parent_chapter",
                "title": "BAB I",
                "full_text": "text",
                "char_count": 4,
                "pasal_count": 1,
                "metadata": {"lang": "id"},
            }
        ]
    )

    assert any("INSERT INTO parent_documents" in query for query, _ in conn.executed)


@pytest.mark.asyncio
async def test_close_pool(monkeypatch):
    module = _load_module(monkeypatch)
    indexer = module.HierarchicalIndexer(_DummyParser({}), _DummyQdrant(), _DummyEmbeddings())
    pool = _DummyPool(_DummyConn())
    indexer.db_pool = pool

    await indexer.close()

    assert pool.closed is True
