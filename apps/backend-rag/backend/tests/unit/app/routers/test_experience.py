"""Tests for backend.app.routers.experience.

Exercises the HTTP contract of /api/experience/* against a FastAPI TestClient
with a real ExperienceService backed by a temp SQLite path.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers.experience import get_experience_service, router
from backend.services.experience.service import ExperienceService


@pytest.fixture
def service(tmp_path) -> ExperienceService:
    return ExperienceService(db_path=str(tmp_path / "router.db"))


@pytest.fixture
def app(service: ExperienceService) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_experience_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "zero@balizero.com", "role": "admin",
    }
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ─── POST /record ─────────────────────────────────────────────────────


def test_record_happy_path(client):
    payload = {
        "trajectory_id": "run_1",
        "cell": "curator",
        "outcome": "success",
        "procedure": "Published ig carousel cleanly.",
        "tokens": 1200,
        "duration_ms": 7000,
        "tags": ["ig", "carousel"],
        "confidence": 0.8,
    }
    resp = client.post("/api/experience/record", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "inserted"
    assert data["trajectory_id"] == "run_1"


def test_record_is_idempotent(client):
    payload = {
        "trajectory_id": "dup",
        "cell": "c",
        "outcome": "success",
        "procedure": "same body",
    }
    first = client.post("/api/experience/record", json=payload)
    second = client.post("/api/experience/record", json=payload)
    assert first.json()["action"] == "inserted"
    assert second.json()["action"] == "updated"


def test_record_rejects_invalid_outcome(client):
    payload = {
        "trajectory_id": "bad",
        "cell": "c",
        "outcome": "maybe",
        "procedure": "invalid",
    }
    resp = client.post("/api/experience/record", json=payload)
    assert resp.status_code == 422


def test_record_rejects_empty_procedure(client):
    payload = {
        "trajectory_id": "t",
        "cell": "c",
        "outcome": "success",
        "procedure": "",
    }
    resp = client.post("/api/experience/record", json=payload)
    assert resp.status_code == 422


def test_record_requires_auth(service):
    """Without the get_current_user override, the endpoint returns 401/403."""
    from backend.app.routers.experience import router as exp_router
    app = FastAPI()
    app.include_router(exp_router)
    app.dependency_overrides[get_experience_service] = lambda: service
    # Deliberately no override for get_current_user — use the real dependency
    client = TestClient(app)
    resp = client.post("/api/experience/record", json={
        "trajectory_id": "x", "cell": "c",
        "outcome": "success", "procedure": "x",
    })
    assert resp.status_code in (401, 403)


# ─── POST /query ──────────────────────────────────────────────────────


def test_query_returns_matching_trajectories(client):
    client.post("/api/experience/record", json={
        "trajectory_id": "t1", "cell": "c1", "outcome": "success",
        "procedure": "DLP scan blocked the draft caption.",
    })
    client.post("/api/experience/record", json={
        "trajectory_id": "t2", "cell": "c1", "outcome": "success",
        "procedure": "Morning photo selected from GARUDA.",
    })
    resp = client.post("/api/experience/query", json={"query": "DLP"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["trajectory_id"] == "t1"


def test_query_filter_by_outcome(client):
    client.post("/api/experience/record", json={
        "trajectory_id": "ok", "cell": "c", "outcome": "success",
        "procedure": "published prose",
    })
    client.post("/api/experience/record", json={
        "trajectory_id": "ko", "cell": "c", "outcome": "failure",
        "procedure": "published prose",
    })
    resp = client.post("/api/experience/query", json={
        "query": "published", "outcome": "failure",
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["trajectory_id"] == "ko"


def test_query_limit_cap(client):
    """Limit > 100 must be rejected (422) — avoids unbounded FTS scans."""
    resp = client.post("/api/experience/query", json={"query": "x", "limit": 10_000})
    assert resp.status_code == 422


# ─── GET /{trajectory_id} ─────────────────────────────────────────────


def test_get_trajectory_by_id(client):
    client.post("/api/experience/record", json={
        "trajectory_id": "lookup",
        "cell": "c",
        "outcome": "success",
        "procedure": "find me",
        "tokens": 42,
    })
    resp = client.get("/api/experience/lookup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trajectory_id"] == "lookup"
    assert body["tokens"] == 42


def test_get_trajectory_404_when_missing(client):
    resp = client.get("/api/experience/missing")
    assert resp.status_code == 404


# ─── GET /stats ───────────────────────────────────────────────────────


def test_stats_endpoint(client):
    for i, oc in enumerate(("success", "success", "failure")):
        client.post("/api/experience/record", json={
            "trajectory_id": f"t_{i}",
            "cell": "c",
            "outcome": oc,
            "procedure": "p",
        })
    resp = client.get("/api/experience/stats?cell=c")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["by_outcome"]["success"] == 2
    assert data["by_outcome"]["failure"] == 1
