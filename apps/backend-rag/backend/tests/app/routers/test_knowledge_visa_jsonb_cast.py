"""Integration tests for knowledge_visa.py's jsonb/text[] cast bug (ex #31).

Root cause: visa_types.requirements/restrictions/allowed_activities/
benefits/process_steps/tips are native Postgres `text[]` columns (verified
via information_schema, 2026-07-20) — NOT jsonb. POST and PUT both cast
those params `::text::jsonb`, which is a hard Postgres type error against a
text[] column ("column X is of type text[] but expression is of type
jsonb"). A mocked-pool unit test cannot catch this — the failure is a real
SQL type mismatch, not a Python-level one — so this test runs against a
real Postgres, matching this repo's own "reproduce the bug on the real call
path" lesson (apps/backend-rag/CLAUDE.md, Migration Runner scar).

Skips cleanly if the DB/table/columns are unreachable or unmigrated.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import backend.app.routers.knowledge_visa as knowledge_visa_module
from backend.app.dependencies import get_database_pool

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

_ARRAY_FIELDS = (
    "requirements",
    "restrictions",
    "allowed_activities",
    "benefits",
    "process_steps",
    "tips",
)


async def _init_jsonb_codec(conn: asyncpg.Connection) -> None:
    """Match backend/app/core/database.py::get_db_pool's init callback — the
    production pool registers a jsonb/json codec (encoder/decoder=json).
    Without it, the fixture pool would round-trip jsonb columns as raw
    strings, silently diverging from what the real app dependency does.
    """
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


@pytest_asyncio.fixture(scope="function")
async def pool() -> AsyncGenerator[asyncpg.Pool, None]:
    try:
        p = await asyncpg.create_pool(
            _DB_URL, min_size=1, max_size=5, init=_init_jsonb_codec
        )
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB unreachable: {exc}")
        return

    skip_reason: str | None = None
    try:
        async with p.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='visa_types')",
            )
            if not exists:
                skip_reason = "visa_types table missing in test DB"
            else:
                for field in _ARRAY_FIELDS:
                    udt = await conn.fetchval(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_name='visa_types' AND column_name=$1",
                        field,
                    )
                    if udt != "_text":
                        skip_reason = (
                            f"visa_types.{field} is '{udt}', expected native "
                            "text[] ('_text') — schema drifted from what this "
                            "test asserts"
                        )
                        break
        if skip_reason is None:
            yield p
    finally:
        await p.close()
    if skip_reason:
        pytest.skip(skip_reason)


def _make_app(pool: asyncpg.Pool) -> FastAPI:
    application = FastAPI()
    application.include_router(knowledge_visa_module.router)
    application.dependency_overrides[get_database_pool] = lambda: pool
    application.dependency_overrides[knowledge_visa_module.get_admin_user] = lambda: {
        "id": "1",
        "email": "zero@balizero.com",
        "role": "admin",
    }
    return application


async def _cleanup(pool: asyncpg.Pool, visa_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM visa_types WHERE id = $1", visa_id)


@pytest.mark.asyncio
async def test_create_then_update_array_and_jsonb_fields_round_trip(
    pool: asyncpg.Pool,
) -> None:
    """Guilt case: before the fix, both POST and PUT 500'd with a Postgres
    type error the instant an array field (e.g. allowed_activities) or a
    genuine jsonb field (cost_details) was set — the ::text::jsonb cast
    against a text[] column is invalid DDL, unconditionally, for any value.
    """
    app = _make_app(pool)
    transport = ASGITransport(app=app)
    code = f"TEST-{uuid.uuid4().hex[:8].upper()}"

    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        created = await ac.post(
            "/api/knowledge/visa/",
            json={
                "code": code,
                "name": "Test Visa",
                "category": "Business",
                "requirements": ["Passport", "Photo"],
                "restrictions": ["No employment"],
                "allowed_activities": ["Business meetings"],
                "benefits": ["Multiple entry"],
                "process_steps": ["Apply", "Pay", "Collect"],
                "tips": ["Bring extra copies"],
                "cost_details": {"visa_fee": 500000, "service_fee": 300000},
            },
        )
        assert created.status_code == 200, created.text
        body = created.json()
        visa_id = body["id"]
        try:
            # Array fields round-tripped as native lists, not JSON-string blobs.
            assert body["requirements"] == ["Passport", "Photo"]
            assert body["allowed_activities"] == ["Business meetings"]
            # Genuine jsonb field round-tripped as a dict.
            assert body["cost_details"] == {
                "visa_fee": 500000,
                "service_fee": 300000,
            }

            updated = await ac.put(
                f"/api/knowledge/visa/{visa_id}",
                json={
                    "allowed_activities": ["Business meetings", "Site visits"],
                    "restrictions": ["No employment", "No enrollment in school"],
                    "metadata": {"reviewed_by": "test"},
                },
            )
            assert updated.status_code == 200, updated.text
            updated_body = updated.json()
            assert updated_body["allowed_activities"] == [
                "Business meetings",
                "Site visits",
            ]
            assert updated_body["restrictions"] == [
                "No employment",
                "No enrollment in school",
            ]
            assert updated_body["metadata"] == {"reviewed_by": "test"}
            # Untouched array field survives the partial update unchanged.
            assert updated_body["requirements"] == ["Passport", "Photo"]
        finally:
            await _cleanup(pool, visa_id)
