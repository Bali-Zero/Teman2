import pytest
from fastapi.testclient import TestClient
from cell_observatory.api import build_app


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("OBSERVATORY_API_KEY", "secret123")
    monkeypatch.setenv("OBSERVATORY_DB_PATH", str(tmp_path / "x.db"))
    app, _ = await build_app()
    yield app


def test_health_unauth(app):
    client = TestClient(app)
    resp = client.get("/api/observatory/health")
    assert resp.status_code == 401


def test_health_authed(app):
    client = TestClient(app)
    resp = client.get("/api/observatory/health", headers={"X-Observatory-Key": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["alive"] is True
