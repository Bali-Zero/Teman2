"""Tests for API routes — query, stream, and health endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from nuzantara_graph.main import app
from nuzantara_graph.graph.builder import build_graph
from helpers.mocks import make_mock_services


def _make_test_llm():
    """LLM mock for API integration tests."""
    call_count = 0

    def _llm(prompt, system):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "intent": "general",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }
        elif "reasoning engine" in system.lower():
            return {
                "steps": [
                    {"step_type": "thought", "content": "Analyzing query"},
                    {"step_type": "observation", "content": "Found info"},
                ],
            }
        elif "zantara" in system.lower():
            return {
                "answer": "Here is the test answer.",
                "sources": [{"title": "Test Source", "id": "t1"}],
                "confidence": {
                    "retrieval_relevance": 0.8,
                    "source_authority": 0.7,
                    "reasoning_coherence": 0.8,
                    "factual_grounding": 0.8,
                    "domain_coverage": 0.7,
                    "answer_completeness": 0.7,
                },
            }

    return _llm


@pytest.fixture
def test_services():
    return make_mock_services(
        llm_responses={"generate_json": _make_test_llm()},
    )


@pytest.fixture
def client(test_services):
    """Create a test client with mocked services and compiled graph."""
    from contextlib import asynccontextmanager

    # Override lifespan to inject mock services
    @asynccontextmanager
    async def _test_lifespan(a):
        graph = build_graph(services=test_services)
        a.state.services = test_services
        a.state.compiled_graph = graph.compile()
        yield

    app.router.lifespan_context = _test_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHealthEndpoints:
    def test_health_returns_healthy(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["embeddings"]["model"] == "text-embedding-3-small"

    def test_readiness_probe(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data


class TestQueryEndpoint:
    def test_query_returns_answer(self, client):
        resp = client.post(
            "/api/query",
            json={"query": "What is a PT PMA?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"]
        assert data["answer"] != ""
        assert data["intent"] == "general"

    def test_query_empty_rejected(self, client):
        resp = client.post(
            "/api/query",
            json={"query": ""},
        )
        assert resp.status_code == 422

    def test_query_with_channel(self, client):
        resp = client.post(
            "/api/query",
            json={"query": "Hello", "channel": "telegram"},
        )
        assert resp.status_code == 200

    def test_query_with_user_id(self, client):
        resp = client.post(
            "/api/query",
            json={"query": "Test", "user_id": "user123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"]


class TestStreamEndpoint:
    def test_stream_returns_sse(self, client):
        resp = client.post(
            "/api/query/stream",
            json={"query": "What is PPN?"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE events
        body = resp.text
        assert "event:" in body
        assert "data:" in body
        # Should contain node_start and done events
        assert "node_start" in body
        assert "done" in body

    def test_stream_contains_node_events(self, client):
        resp = client.post(
            "/api/query/stream",
            json={"query": "How to set up company?"},
        )
        body = resp.text
        events = [
            line for line in body.split("\n")
            if line.startswith("event:")
        ]
        # Should have multiple node events
        assert len(events) >= 3  # at least start, some nodes, done


class TestRequestTracing:
    def test_response_has_request_id(self, client):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers

    def test_custom_request_id_preserved(self, client):
        resp = client.get(
            "/health",
            headers={"X-Request-ID": "test-123"},
        )
        assert resp.headers.get("x-request-id") == "test-123"

    def test_response_has_timing(self, client):
        resp = client.get("/health")
        assert "x-response-time-ms" in resp.headers
