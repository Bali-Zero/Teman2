"""Tests for /api/jobs admin endpoints via FastAPI TestClient."""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers.jobs_admin import build_router
from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


@pytest.fixture
async def app_client(pg_pool, monkeypatch):
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key")

    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult(ok=True, meta={"ran": True})

    reg.register(name="t", cron="*/5 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set())

    app = FastAPI()
    app.include_router(build_router(runner=runner))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        yield ac


async def test_get_jobs_lists_registry(app_client):
    r = await app_client.get("/api/jobs", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    data = r.json()
    assert any(j["name"] == "t" for j in data["jobs"])


async def test_get_jobs_requires_api_key(app_client):
    r = await app_client.get("/api/jobs")
    assert r.status_code == 401


async def test_post_run_executes_job(app_client):
    r = await app_client.post("/api/jobs/t/run", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert isinstance(body["run_id"], int)


async def test_get_runs_returns_history(app_client):
    await app_client.post("/api/jobs/t/run", headers={"X-API-Key": "test-key"})
    r = await app_client.get("/api/jobs/t/runs?limit=5", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert len(runs) >= 1


async def test_unknown_job_name_returns_404(app_client):
    r = await app_client.post("/api/jobs/nope/run", headers={"X-API-Key": "test-key"})
    assert r.status_code == 404
