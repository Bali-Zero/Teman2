"""Integration tests for the INTAKE gate doc-count mirror (Pro→Fly, task #19).

Covers:
- POST /api/bridge/intake-gate/doc-counts (upsert + zero-absent + auth)
- gate_evaluator mirror mode (INTAKE_GATE_USE_MIRROR) reads the mirror table,
  honors staleness, and blocks/clears accordingly.

Real Postgres (nuzantara_dev). Rows committed + cleaned in teardown. Skips
cleanly if the mirror table (migration 219) is absent.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.database import get_database_pool
from backend.app.routers.bridge import router as bridge_router
from backend.services.intake.gate_evaluator import evaluate_gate_status

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_dev"
)
_BRIDGE_KEY = "test-bridge-key-219"


def make_app(pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI()
    app.include_router(bridge_router)

    async def fake_pool():
        return pool

    app.dependency_overrides[get_database_pool] = fake_pool
    return app


@pytest_asyncio.fixture(scope="function")
async def pool() -> AsyncGenerator[asyncpg.Pool, None]:
    try:
        p = await asyncpg.create_pool(_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB unreachable: {exc}")
        return
    skip_reason: str | None = None
    try:
        async with p.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='intake_gate_doc_counts')"
            )
            if not exists:
                skip_reason = "intake_gate_doc_counts missing (migration 219 not applied)"
        if skip_reason is None:
            yield p
    finally:
        await p.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture
async def emails(pool: asyncpg.Pool):
    used: list[str] = []
    yield used
    if used:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM intake_gate_doc_counts WHERE user_email = ANY($1::text[])",
                [e.lower() for e in used],
            )


@pytest.mark.asyncio
async def test_push_upserts_and_zeroes_absent(pool, emails, monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", _BRIDGE_KEY)
    a = f"push-a-{uuid.uuid4().hex[:8]}@balizero.com"
    b = f"push-b-{uuid.uuid4().hex[:8]}@balizero.com"
    emails += [a, b]

    app = make_app(pool)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        # First push: a=3, b=2
        r = await ac.post(
            "/api/bridge/intake-gate/doc-counts",
            headers={"X-Bridge-Auth": _BRIDGE_KEY},
            json={"counts": [{"user_email": a, "pending_count": 3},
                             {"user_email": b, "pending_count": 2}]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["upserted"] == 2

        # Second push: only a=1 → b must be zeroed (absent from snapshot).
        r2 = await ac.post(
            "/api/bridge/intake-gate/doc-counts",
            headers={"X-Bridge-Auth": _BRIDGE_KEY},
            json={"counts": [{"user_email": a, "pending_count": 1}]},
        )
        assert r2.status_code == 200
        assert r2.json()["zeroed"] == 1

    async with pool.acquire() as conn:
        ca = await conn.fetchval(
            "SELECT pending_count FROM intake_gate_doc_counts WHERE user_email=$1", a
        )
        cb = await conn.fetchval(
            "SELECT pending_count FROM intake_gate_doc_counts WHERE user_email=$1", b
        )
    assert ca == 1
    assert cb == 0


@pytest.mark.asyncio
async def test_push_requires_auth(pool):
    app = make_app(pool)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/bridge/intake-gate/doc-counts",
            headers={"X-Bridge-Auth": "wrong"},
            json={"counts": []},
        )
    # 401 invalid creds (or 503 if BRIDGE_API_KEY unset in this env).
    assert r.status_code in (401, 503)


@pytest.mark.asyncio
async def test_evaluator_mirror_mode_blocks_and_respects_staleness(pool, emails, monkeypatch):
    email = f"mirror-{uuid.uuid4().hex[:8]}@balizero.com"
    emails.append(email)
    monkeypatch.setenv("INTAKE_GATE_USE_MIRROR", "1")

    # Fresh mirror row with 2 pending → blocked via the mirror path.
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO intake_gate_doc_counts (user_email, pending_count, updated_at) "
            "VALUES ($1, 2, now())",
            email,
        )
    result = await evaluate_gate_status(pool, user_email=email, is_admin=False)
    assert result["sections"]["documents"]["count"] == 2
    assert result["blocked"] is True

    # Make the row stale (older than the 6h window) → treated as 0.
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE intake_gate_doc_counts SET updated_at = now() - interval '7 hours' "
            "WHERE user_email=$1",
            email,
        )
    stale = await evaluate_gate_status(pool, user_email=email, is_admin=False)
    assert stale["sections"]["documents"]["count"] == 0
