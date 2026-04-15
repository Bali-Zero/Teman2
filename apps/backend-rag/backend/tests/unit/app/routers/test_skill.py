"""Tests for backend.app.routers.skill.

HTTP contract of /api/skill/* against a FastAPI TestClient with a real
SkillService backed by a temp SQLite path.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers.skill import get_skill_service, router
from backend.services.skill.service import SkillService


@pytest.fixture
def service(tmp_path) -> SkillService:
    return SkillService(db_path=str(tmp_path / "skill.db"))


@pytest.fixture
def app(service: SkillService) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_skill_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "zero@balizero.com", "role": "admin",
    }
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _record_payload(**overrides):
    base = {
        "cell": "rag",
        "skill_id": "rag:rrf",
        "procedure": "Combine BM25 + dense vector retrieval via RRF.",
        "precondition": "Both indices populated.",
        "success_criterion": "Top-5 recall > 0.85.",
        "confidence": 0.75,
    }
    base.update(overrides)
    return base


# ─── POST /record ────────────────────────────────────────────────────


def test_record_happy_path(client):
    resp = client.post("/api/skill/record", json=_record_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "inserted"
    assert body["skill_id"] == "rag:rrf"


def test_record_is_idempotent(client):
    first = client.post("/api/skill/record", json=_record_payload())
    second = client.post("/api/skill/record", json=_record_payload())
    assert first.json()["action"] == "inserted"
    assert second.json()["action"] == "updated"


def test_record_rejects_empty_procedure(client):
    resp = client.post("/api/skill/record", json=_record_payload(procedure=""))
    assert resp.status_code == 422


def test_record_rejects_out_of_range_confidence(client):
    resp = client.post("/api/skill/record", json=_record_payload(confidence=1.5))
    assert resp.status_code == 422


def test_record_requires_auth(service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_skill_service] = lambda: service
    client = TestClient(app)
    resp = client.post("/api/skill/record", json=_record_payload())
    assert resp.status_code in (401, 403)


# ─── POST /query ─────────────────────────────────────────────────────


def test_query_returns_matching(client):
    client.post("/api/skill/record", json=_record_payload(
        skill_id="a", procedure="DLP pre-publish scan body.",
    ))
    client.post("/api/skill/record", json=_record_payload(
        skill_id="b", procedure="Chunk text into overlapping windows.",
    ))
    resp = client.post("/api/skill/query", json={"query": "DLP"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["skill_id"] == "a"


def test_query_limit_cap_422(client):
    resp = client.post("/api/skill/query", json={"query": "x", "limit": 10_000})
    assert resp.status_code == 422


def test_query_filters_tier_and_min_conf(client):
    # Record two skills, promote one to tier1 directly via DB.
    client.post("/api/skill/record", json=_record_payload(
        skill_id="hot", procedure="hot prose alpha", confidence=0.9,
    ))
    client.post("/api/skill/record", json=_record_payload(
        skill_id="cold", procedure="hot prose bravo", confidence=0.4,
    ))
    import sqlite3
    # Reach into the service's own db (fixture wired it this way)
    svc = client.app.dependency_overrides[get_skill_service]()
    conn = sqlite3.connect(svc._db_path)
    conn.execute("UPDATE genome SET tier='tier1' WHERE id='hot'")
    conn.commit()
    conn.close()

    resp = client.post("/api/skill/query", json={
        "query": "prose", "tier": "tier1", "min_confidence": 0.5,
    })
    assert resp.status_code == 200
    ids = [r["skill_id"] for r in resp.json()["results"]]
    assert ids == ["hot"]


# ─── GET /stats ──────────────────────────────────────────────────────


def test_stats_endpoint(client):
    for i in range(3):
        client.post("/api/skill/record", json=_record_payload(
            skill_id=f"s{i}", procedure=f"proc {i}",
        ))
    resp = client.get("/api/skill/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert "by_tier" in data
    assert "by_cell" in data


# ─── GET /top ────────────────────────────────────────────────────────


def test_top_endpoint_defaults_tier1(client):
    client.post("/api/skill/record", json=_record_payload(
        skill_id="t1only", procedure="promoted body", confidence=0.95,
    ))
    import sqlite3
    svc = client.app.dependency_overrides[get_skill_service]()
    conn = sqlite3.connect(svc._db_path)
    conn.execute("UPDATE genome SET tier='tier1' WHERE id='t1only'")
    conn.commit()
    conn.close()

    resp = client.get("/api/skill/top")
    assert resp.status_code == 200
    ids = [r["skill_id"] for r in resp.json()["results"]]
    assert ids == ["t1only"]


def test_top_endpoint_rejects_invalid_tier(client):
    resp = client.get("/api/skill/top?tier=tier3")
    assert resp.status_code == 422


# ─── GET /merge-proposals ────────────────────────────────────────────


def test_merge_proposals_empty_by_default(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.services.skill.service.MERGE_PROPOSALS_PATH",
        str(tmp_path / "nope.jsonl"),
    )
    resp = client.get("/api/skill/merge-proposals")
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "proposals": []}


def test_merge_proposals_reads_written_file(client, monkeypatch, tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text(
        json.dumps({"pair": ["a", "b"], "cosine": 0.09}) + "\n"
    )
    monkeypatch.setattr(
        "backend.services.skill.service.MERGE_PROPOSALS_PATH", str(path),
    )
    resp = client.get("/api/skill/merge-proposals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["proposals"][0]["pair"] == ["a", "b"]


# ─── GET /{skill_id} ─────────────────────────────────────────────────


def test_get_by_id(client):
    client.post("/api/skill/record", json=_record_payload(skill_id="findme"))
    resp = client.get("/api/skill/findme")
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill_id"] == "findme"


def test_get_by_id_404(client):
    resp = client.get("/api/skill/does-not-exist")
    assert resp.status_code == 404
