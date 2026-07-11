from __future__ import annotations

import json
from pathlib import Path

from backend.services.ingestion.politics_ingestion import PoliticsIngestionService


class FakeEmbedder:
    def generate_embeddings(self, documents: list[str]) -> list[list[float]]:
        return [[float(index)] for index, _document in enumerate(documents)]


class FakeVectorDB:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def upsert_documents(
        self,
        *,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, object]],
        ids: list[str],
    ) -> None:
        self.calls.append(
            {
                "chunks": chunks,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "ids": ids,
            }
        )


def build_service() -> PoliticsIngestionService:
    service = PoliticsIngestionService.__new__(PoliticsIngestionService)
    service.embedder = FakeEmbedder()
    service.vector_db = FakeVectorDB()
    return service


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_build_text_formats_known_record_types() -> None:
    service = build_service()

    assert "Tokoh: Ada" in service._build_text({"type": "person", "name": "Ada"})
    assert "Partai: Demo" in service._build_text({"type": "party", "name": "Demo"})
    assert "Pemilu: election-1" in service._build_text(
        {"type": "election", "id": "election-1"}
    )
    assert "Yurisdiksi: bali Bali" in service._build_text(
        {"type": "jurisdiction", "id": "bali", "name": "Bali"}
    )
    assert "Regulasi: 1 Tax Rule" in service._build_text(
        {"type": "law", "number": "1", "title": "Tax Rule"}
    )
    assert service._build_text({"type": "other", "id": "x"}) == '{"type": "other", "id": "x"}'


def test_ingest_jsonl_files_embeds_and_upserts_valid_records(tmp_path) -> None:
    file_path = tmp_path / "records.jsonl"
    write_jsonl(
        file_path,
        [
            {
                "type": "person",
                "id": "person-1",
                "name": "Ada",
                "sources": [{"url": "source"}],
            },
            {"type": "party", "name": "Demo"},
        ],
    )
    service = build_service()

    result = service.ingest_jsonl_files([file_path])

    assert result == {"success": True, "documents_added": 2}
    call = service.vector_db.calls[0]
    assert call["embeddings"] == [[0.0], [1.0]]
    assert call["metadatas"][0]["record_id"] == "person-1"
    assert call["metadatas"][0]["source_count"] == 1
    assert call["ids"][0] == "pol:person:person-1:0"
    assert call["ids"][1] == "pol:party:record:records:1:1"


def test_ingest_jsonl_files_returns_false_for_empty_or_unreadable_files(tmp_path) -> None:
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("\n", encoding="utf-8")
    service = build_service()

    assert service.ingest_jsonl_files([empty_file]) == {
        "success": False,
        "documents_added": 0,
        "message": "No records found",
    }
    assert service.ingest_jsonl_files([tmp_path / "missing.jsonl"]) == {
        "success": False,
        "documents_added": 0,
        "message": "No records found",
    }


def test_ingest_dir_collects_standard_subdirectories(tmp_path, monkeypatch) -> None:
    root = tmp_path / "politics"
    persons = root / "persons"
    parties = root / "parties"
    ignored = root / "other"
    persons.mkdir(parents=True)
    parties.mkdir()
    ignored.mkdir()
    (persons / "a.jsonl").write_text("{}\n", encoding="utf-8")
    (parties / "b.jsonl").write_text("{}\n", encoding="utf-8")
    (ignored / "c.jsonl").write_text("{}\n", encoding="utf-8")
    service = build_service()
    seen_paths: list[Path] = []

    def fake_ingest(paths: list[Path]) -> dict[str, object]:
        seen_paths.extend(paths)
        return {"success": True, "documents_added": len(paths)}

    monkeypatch.setattr(service, "ingest_jsonl_files", fake_ingest)

    assert service.ingest_dir(root) == {"success": True, "documents_added": 2}
    assert seen_paths == [persons / "a.jsonl", parties / "b.jsonl"]
