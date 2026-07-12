"""
Unit tests for GET /api/agents/knowledge-graph/export.

Regression test for a live production 500:
  RuntimeWarning: coroutine 'KnowledgeGraphBuilder.export_graph' was never awaited
  Unable to serialize unknown type: <class 'coroutine'>

Root cause: backend/app/routers/agents.py::export_knowledge_graph called the
async `KnowledgeGraphBuilder.export_graph()` without `await`, so FastAPI tried
to JSON-serialize a coroutine object instead of the exported string.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers.agents import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-user",
        "email": "zero@balizero.com",
        "role": "admin",
    }
    return TestClient(app)


def test_export_knowledge_graph_json_returns_string_not_coroutine():
    """The 'data' field must be the awaited string, never a coroutine repr."""
    client = _make_client()
    response = client.get("/api/agents/knowledge-graph/export?format=json")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], str)
    # A coroutine that leaked through str()/repr() would look like
    # "<coroutine object ... at 0x...>" -- guard against that regression shape too.
    assert "coroutine" not in body["data"]


def test_export_knowledge_graph_cypher_format():
    """Non-default format should also resolve to a real string, not a coroutine."""
    client = _make_client()
    response = client.get("/api/agents/knowledge-graph/export?format=neo4j")

    assert response.status_code == 200
    body = response.json()
    assert body["internal_format"] == "cypher"
    assert isinstance(body["data"], str)
    assert "coroutine" not in body["data"]


def test_export_knowledge_graph_graphml_format():
    client = _make_client()
    response = client.get("/api/agents/knowledge-graph/export?format=graphml")

    assert response.status_code == 200
    body = response.json()
    assert body["internal_format"] == "graphml"
    assert isinstance(body["data"], str)
    assert "coroutine" not in body["data"]
