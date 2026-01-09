import importlib.util
import json
import sys
import types
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
module_path = backend_path / "services" / "ingestion" / "politics_ingestion.py"
module_name = "services.ingestion.politics_ingestion"


def _build_module(monkeypatch, embedder_stub, qdrant_stub):
    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = [str(backend_path / "core")]
    monkeypatch.setitem(sys.modules, "core", core_pkg)
    monkeypatch.setitem(
        sys.modules,
        "core.embeddings",
        types.SimpleNamespace(create_embeddings_generator=lambda: embedder_stub, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules, "core.qdrant_db", types.SimpleNamespace(QdrantClient=qdrant_stub, redis_url='redis://localhost:6379')
    )

    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _Embedder:
    def __init__(self):
        self.documents = []

    def generate_embeddings(self, documents):
        self.documents = documents
        return [[0.1, 0.2] for _ in documents]


class _QdrantClient:
    def __init__(self, qdrant_url=None, collection_name=None):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.calls = []

    def upsert_documents(self, chunks, embeddings, metadatas, ids):
        self.calls.append(
            {
                "chunks": chunks,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "ids": ids,
            }
        )


def test_build_text_variants(monkeypatch):
    module = _build_module(monkeypatch, _Embedder(), _QdrantClient)
    service = module.PoliticsIngestionService()

    person = {
        "type": "person",
        "name": "A",
        "dob": "1-1-1990",
        "pob": "X",
        "offices": [{"office": "Mayor", "from": "2000", "to": "2005", "jurisdiction_id": "J1"}],
        "party_memberships": [{"party_id": "P1", "from": "1999", "to": "2001"}],
    }
    assert "Tokoh: A" in service._build_text(person)
    assert "Jabatan:" in service._build_text(person)

    party = {
        "type": "party",
        "name": "Party A",
        "abbrev": "PA",
        "founded": "1999",
        "leaders": [{"person_id": "X", "from": "2000", "to": "2003"}],
        "ideology": ["liberal"],
    }
    assert "Partai: Party A (PA)" in service._build_text(party)
    assert "Ideologi: liberal" in service._build_text(party)

    election = {
        "type": "election",
        "id": "e1",
        "date": "2024-01-01",
        "level": "national",
        "scope": "id",
        "jurisdiction_id": "J1",
        "contests": [
            {
                "office": "Pres",
                "district": "D1",
                "results": [{"candidate_id": "C1", "party_id": "P1", "votes": 10, "pct": 50.0}],
            }
        ],
    }
    text = service._build_text(election)
    assert "Pemilu: e1 pada 2024-01-01" in text
    assert "calon=C1" in text

    jurisdiction = {"type": "jurisdiction", "id": "J1", "name": "Jakarta", "kind": "city"}
    assert "Yurisdiksi: J1 Jakarta (city)" in service._build_text(jurisdiction)

    law = {"type": "law", "number": "1", "title": "Law", "date": "2000-01-01"}
    assert "Regulasi: 1 Law (2000-01-01)" in service._build_text(law)

    fallback = {"type": "other", "name": "X"}
    assert service._build_text(fallback) == json.dumps(fallback, ensure_ascii=False)


def test_ingest_jsonl_files_success(monkeypatch, tmp_path):
    embedder = _Embedder()
    module = _build_module(monkeypatch, embedder, _QdrantClient)
    service = module.PoliticsIngestionService()

    data = [
        {"type": "person", "id": "p1", "name": "A", "sources": ["s1"]},
        {"type": "party", "id": "party1", "name": "Party"},
    ]
    path = tmp_path / "records.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in data))

    result = service.ingest_jsonl_files([path])

    assert result["success"] is True
    assert result["documents_added"] == 2
    assert len(service.vector_db.calls) == 1
    call = service.vector_db.calls[0]
    assert call["metadatas"][0]["record_type"] == "person"
    assert call["metadatas"][0]["source_count"] == 1
    assert embedder.documents[0].startswith("Tokoh:")


def test_ingest_jsonl_files_empty(monkeypatch, tmp_path):
    module = _build_module(monkeypatch, _Embedder(), _QdrantClient)
    service = module.PoliticsIngestionService()

    path = tmp_path / "empty.jsonl"
    path.write_text("\n")

    result = service.ingest_jsonl_files([path])

    assert result["success"] is False
    assert result["documents_added"] == 0
    assert len(service.vector_db.calls) == 0


def test_ingest_dir_collects_files(monkeypatch, tmp_path):
    module = _build_module(monkeypatch, _Embedder(), _QdrantClient)
    service = module.PoliticsIngestionService()

    (tmp_path / "persons").mkdir()
    (tmp_path / "parties").mkdir()
    (tmp_path / "elections").mkdir()
    (tmp_path / "jurisdictions").mkdir()
    target = tmp_path / "persons" / "p.jsonl"
    target.write_text(json.dumps({"type": "person", "id": "p1"}))

    captured = {}

    def _fake_ingest(paths):
        captured["paths"] = paths
        return {"success": True, "documents_added": 1}

    monkeypatch.setattr(service, "ingest_jsonl_files", _fake_ingest)

    result = service.ingest_dir(tmp_path)

    assert result["success"] is True
    assert target in captured["paths"]
