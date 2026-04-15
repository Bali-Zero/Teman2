"""End-to-end HTTP test for the Experience Library.

Exercises record → query → stats → get_by_id against a TestClient session
backed by a real ExperienceService on a temp SQLite path. This is the
deployment smoke test in miniature.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers.experience import get_experience_service, router
from backend.services.experience.service import ExperienceService


@pytest.fixture
def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    svc = ExperienceService(db_path=str(tmp_path / "e2e.db"))
    app.dependency_overrides[get_experience_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "e2e@balizero.com",
    }
    return TestClient(app)


def test_full_lifecycle_record_query_stats_get(client):
    # Step 1 — record three trajectories with distinct outcomes.
    for tid, outcome, proc in (
        ("e2e_1", "success", "Resolved visa query with KBLI 70209."),
        ("e2e_2", "failure", "DLP blocked draft caption — PII detected."),
        ("e2e_3", "partial", "Published 2/3 assets; third timed out on vision scan."),
    ):
        resp = client.post("/api/experience/record", json={
            "trajectory_id": tid,
            "cell": "curator",
            "outcome": outcome,
            "procedure": proc,
            "tags": ["e2e"],
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["action"] == "inserted"

    # Step 2 — query by full-text.
    resp = client.post("/api/experience/query", json={"query": "DLP"})
    assert resp.status_code == 200
    hits = resp.json()["results"]
    assert len(hits) == 1
    assert hits[0]["trajectory_id"] == "e2e_2"
    assert hits[0]["outcome"] == "failure"

    # Step 3 — stats reflect the three records.
    resp = client.get("/api/experience/stats?cell=curator")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total"] == 3
    assert stats["by_outcome"] == {"success": 1, "failure": 1, "partial": 1}

    # Step 4 — get-by-id returns the stored row with tags round-tripped.
    resp = client.get("/api/experience/e2e_1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trajectory_id"] == "e2e_1"
    assert body["tags"] == ["e2e"]

    # Step 5 — get-by-id 404 for unknown id.
    resp = client.get("/api/experience/nope")
    assert resp.status_code == 404


def test_idempotent_post_over_http(client):
    payload = {
        "trajectory_id": "dup_http", "cell": "c",
        "outcome": "success", "procedure": "idempotent over HTTP",
    }
    first = client.post("/api/experience/record", json=payload)
    second = client.post("/api/experience/record", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["action"] == "inserted"
    assert second.json()["action"] == "updated"


def test_outcome_filter_over_http(client):
    for tid, oc in (("a1", "success"), ("b1", "failure"), ("c1", "partial")):
        client.post("/api/experience/record", json={
            "trajectory_id": tid, "cell": "c", "outcome": oc,
            "procedure": "shared wording blob",
        })
    resp = client.post("/api/experience/query", json={
        "query": "shared", "outcome": "failure",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["trajectory_id"] == "b1"
