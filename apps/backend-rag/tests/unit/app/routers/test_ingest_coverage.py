import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch, ingest_results=None, ingest_error=None, stats=None, stats_error=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    class _IngestionService:
        def __init__(self):
            self.calls = []

        async def ingest_book(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            if ingest_error:
                raise ingest_error
            if isinstance(ingest_results, list):
                value = ingest_results.pop(0)
                if isinstance(value, Exception):
                    raise value
                return value
            return ingest_results or {
                "success": True,
                "book_title": "Test Book",
                "book_author": "Author",
                "tier": "A",
                "chunks_created": 1,
                "message": "ok",
                "error": None,
            }

    class _QdrantClient:
        def get_collection_stats(self):
            if stats_error:
                raise stats_error
            return stats or {
                "collection_name": "books",
                "total_documents": 10,
                "tiers_distribution": {"A": 10},
                "persist_directory": "/data/qdrant",
            }

    monkeypatch.setitem(
        sys.modules,
        "backend.services.ingestion.ingestion_service",
        types.SimpleNamespace(IngestionService=_IngestionService, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.core.qdrant_db",
        types.SimpleNamespace(QdrantClient=_QdrantClient, redis_url='redis://localhost:6379'),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("backend.app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "backend.app.routers", routers_pkg)

    module_name = "backend.app.routers.ingest"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "ingest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(router_module):
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def test_upload_rejects_invalid_extension(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/ingest/upload",
        files={"file": ("book.txt", b"data", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_success(monkeypatch, tmp_path):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/ingest/upload",
        files={"file": ("book.pdf", b"data", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_upload_failure(monkeypatch):
    module = _load_module(monkeypatch, ingest_error=RuntimeError("boom"))
    client = _make_client(module)

    response = client.post(
        "/api/ingest/upload",
        files={"file": ("book.pdf", b"data", "application/pdf")},
    )

    assert response.status_code == 500
    assert "Ingestion failed" in response.json()["detail"]


def test_ingest_local_file_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.setattr(module.os.path, "exists", lambda _: False)

    response = client.post("/api/ingest/file", json={"file_path": "/missing.pdf"})

    assert response.status_code == 404


def test_ingest_local_file_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.setattr(module.os.path, "exists", lambda _: True)

    response = client.post(
        "/api/ingest/file",
        json={"file_path": "/book.pdf", "title": "T", "author": "A"},
    )

    assert response.status_code == 200
    assert response.json()["book_title"] == "Test Book"


def test_batch_ingest_directory_missing(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post("/api/ingest/batch", json={"directory_path": "/missing"})

    assert response.status_code == 404


def test_batch_ingest_no_files(monkeypatch, tmp_path):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post("/api/ingest/batch", json={"directory_path": str(tmp_path)})

    assert response.status_code == 400


def test_batch_ingest_mixed_results(monkeypatch, tmp_path):
    results = [
        {
            "success": True,
            "book_title": "Good",
            "book_author": "A",
            "tier": "B",
            "chunks_created": 1,
            "message": "ok",
            "error": None,
        },
        {
            "success": False,
            "book_title": "Bad",
            "book_author": "B",
            "tier": "C",
            "chunks_created": 0,
            "message": "failed",
            "error": "boom",
        },
    ]
    module = _load_module(monkeypatch, ingest_results=results)
    client = _make_client(module)

    (tmp_path / "a.pdf").write_text("data")
    (tmp_path / "b.epub").write_text("data")

    response = client.post("/api/ingest/batch", json={"directory_path": str(tmp_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["total_books"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1


def test_batch_ingest_exception_returns_500(monkeypatch, tmp_path):
    results = [
        {
            "success": True,
            "book_title": "Good",
            "book_author": "A",
            "tier": "B",
            "chunks_created": 1,
            "message": "ok",
            "error": None,
        },
        RuntimeError("fail"),
    ]
    module = _load_module(monkeypatch, ingest_results=results)
    client = _make_client(module)

    (tmp_path / "a.pdf").write_text("data")
    (tmp_path / "b.epub").write_text("data")

    response = client.post("/api/ingest/batch", json={"directory_path": str(tmp_path)})

    assert response.status_code == 500


def test_get_ingestion_stats_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/ingest/stats")

    assert response.status_code == 200
    assert response.json()["total_documents"] == 10


def test_get_ingestion_stats_error(monkeypatch):
    module = _load_module(monkeypatch, stats_error=RuntimeError("bad"))
    client = _make_client(module)

    response = client.get("/api/ingest/stats")

    assert response.status_code == 500
    assert "Failed to get stats" in response.json()["detail"]
