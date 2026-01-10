import importlib.util
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(
    monkeypatch,
    search_results=None,
    peek_results=None,
    stats_results=None,
    search_errors=None,
    stats_errors=None,
):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    class _Embedder:
        def generate_single_embedding(self, _query):
            return [0.1, 0.2]

    class _QdrantClient:
        upsert_calls = []

        def __init__(self, collection_name):
            self.collection_name = collection_name

        async def search(self, query_embedding, filter, limit):
            if self.collection_name in (search_errors or set()):
                raise RuntimeError("search error")
            return (search_results or {}).get(
                self.collection_name, {"documents": [], "metadatas": [], "distances": []}
            )

        async def upsert_documents(self, chunks, embeddings, metadatas, ids):
            self.upsert_calls.append(
                {"chunks": chunks, "embeddings": embeddings, "metadatas": metadatas, "ids": ids}
            )

        async def peek(self, limit=100):
            return (peek_results or {}).get(self.collection_name, {"metadatas": []})

        def get_collection_stats(self):
            if self.collection_name in (stats_errors or set()):
                raise RuntimeError("stats error")
            return (stats_results or {}).get(self.collection_name, {"total_documents": 0})

    class _Settings:
        def __init__(self):
            self.get_intel_staging_base_dir = "/tmp/staging"
            self.get_intel_pending_path = "/tmp/pending_intel"
            self.qdrant_url = "http://localhost:6333"
            self.qdrant_api_key = None
            self.redis_url = 'redis://localhost:6379'
            self.jwt_secret_key = "test_secret_at_least_32_chars_long_"
            self.jwt_algorithm = "HS256"

        def __getattr__(self, name):
            return None

    config_mock = types.ModuleType("backend.app.core.config")
    config_mock.settings = _Settings()
    config_mock.Settings = _Settings
    monkeypatch.setitem(sys.modules, "backend.app.core.config", config_mock)

    monkeypatch.setitem(
        sys.modules,
        "backend.core.embeddings",
        types.SimpleNamespace(
            create_embeddings_generator=lambda **kwargs: _Embedder(),
            EmbeddingsGenerator=_Embedder,
            redis_url='redis://localhost:6379'
        ),
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

    module_name = "backend.app.routers.intel"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "intel.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, _QdrantClient


def _make_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_search_intel_success(monkeypatch):
    collection = "bali_intel_immigration"
    search_results = {
        collection: {
            "documents": ["doc"],
            "metadatas": [
                {
                    "id": "1",
                    "title": "Title",
                    "summary_italian": "Riassunto",
                    "source": "source",
                    "tier": "T1",
                    "published_date": "2025-01-01",
                    "impact_level": "low",
                    "url": "url",
                    "key_changes": [],
                    "action_required": "True",
                    "deadline_date": None,
                }
            ],
            "distances": [0.5],
        }
    }
    module, _ = _load_module(monkeypatch, search_results=search_results)
    client = _make_client(module)

    response = client.post("/api/intel/search", json={"query": "news", "category": "immigration"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["category"] == "immigration"
    assert data["results"][0]["action_required"] is True


def test_search_intel_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.setattr(
        module.embedder,
        "generate_single_embedding",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post("/api/intel/search", json={"query": "news"})

    assert response.status_code == 500


def test_store_intel_invalid_collection(monkeypatch):
    module, _ = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/intel/store",
        json={
            "collection": "unknown",
            "id": "1",
            "document": "doc",
            "embedding": [0.1],
            "metadata": {},
            "full_data": {},
        },
    )

    assert response.status_code == 500


def test_store_intel_success(monkeypatch):
    module, qdrant = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/intel/store",
        json={
            "collection": "immigration",
            "id": "1",
            "document": "doc",
            "embedding": [0.1],
            "metadata": {"id": "1"},
            "full_data": {},
        },
    )

    assert response.status_code == 200
    assert qdrant.upsert_calls


def test_get_critical_items(monkeypatch):
    collection = "bali_intel_immigration"
    cutoff = (datetime.now() + timedelta(days=1)).isoformat()
    peek_results = {
        collection: {
            "metadatas": [
                {
                    "id": "1",
                    "title": "Critical",
                    "impact_level": "critical",
                    "published_date": cutoff,
                },
                {
                    "id": "2",
                    "title": "Low",
                    "impact_level": "low",
                    "published_date": cutoff,
                },
            ]
        }
    }
    module, _ = _load_module(monkeypatch, peek_results=peek_results)
    client = _make_client(module)

    response = client.get("/api/intel/critical", params={"category": "immigration"})

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["items"][0]["title"] == "Critical"


def test_get_trends(monkeypatch):
    stats_results = {
        "bali_intel_immigration": {"total_documents": 3},
        "bali_intel_realestate": {"total_documents": 2},
    }
    module, _ = _load_module(
        monkeypatch, stats_results=stats_results, stats_errors={"bali_intel_events"}
    )
    client = _make_client(module)

    response = client.get("/api/intel/trends")

    assert response.status_code == 200
    data = response.json()
    assert any(item["total_items"] == 3 for item in data["trends"])


def test_get_collection_stats(monkeypatch):
    stats_results = {"bali_intel_immigration": {"total_documents": 5}}
    module, _ = _load_module(monkeypatch, stats_results=stats_results)
    client = _make_client(module)

    response = client.get("/api/intel/stats/immigration")

    assert response.status_code == 200
    assert response.json()["total_documents"] == 5

    response = client.get("/api/intel/stats/unknown")

    assert response.status_code == 500
