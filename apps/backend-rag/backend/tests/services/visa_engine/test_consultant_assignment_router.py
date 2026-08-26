"""HTTP-level tests for ``POST /api/visa-oracle/consultant-assignment``.

V3/unit-2 deliverable, router half. Mirrors ``test_evaluate_endpoint.py``'s
``_build_app``/``_client``/``ASGITransport`` convention: a bare FastAPI app
with only this router mounted and ``app.state.db_pool`` set directly (the
same seam ``get_database_pool`` reads — no dependency-override needed).

One drift from the original dispatch brief worth recording here rather than
silently "fixing" the brief: the brief asked for a test proving a
"malformed/PII-shaped body is rejected via C3's own guard, surfacing as a
400". In practice ``ConsultantAssignmentRequestBody`` already mirrors C3's
closed types and ``extra="forbid"`` at the FastAPI-schema layer, so a
PII-shaped or unknown key never reaches ``ConsultantAssignmentEvent``
reconstruction at all — FastAPI itself rejects it with **422** before the
router body ever runs. The router's own ``try/except ValidationError`` (->
400) is real defense-in-depth but is not reachable through this HTTP
surface today, precisely because the two schemas are kept in lockstep on
purpose. Tests below assert the shape that is actually true (422 at the
API boundary), not the one assumed in the brief.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from backend.app.routers import visa_oracle_consultant
from backend.db.migration_base import split_migration_sql
from backend.services.visa_engine import consultant_assignment_service

pytestmark = pytest.mark.asyncio

_MIGRATION_281_PATH = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "293_visa_oracle_consultant_requests.sql"
)
_TEARDOWN_281_SQL = """
DROP TRIGGER IF EXISTS trg_guard_visa_oracle_consultant_requests_append_only
    ON public.visa_oracle_consultant_requests;
DROP FUNCTION IF EXISTS public.guard_visa_oracle_consultant_requests_append_only();
DROP TABLE IF EXISTS public.visa_oracle_consultant_requests;
"""
_DEFAULT_DB_URL = "postgresql://nuzantara@localhost:5432/nuzantara_test"


def _build_app(db_pool: object) -> FastAPI:
    app = FastAPI()
    app.include_router(visa_oracle_consultant.router)
    app.state.db_pool = db_pool
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _valid_body(**overrides: object) -> dict:
    base: dict[str, object] = {
        "evaluation_id": str(uuid.uuid4()),
        "origin_screen": "verdict",
        "tier": "T2",
        "locale": "en",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Success path — needs a real DB (migration 281 applied)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture(scope="function")
async def consultant_requests_schema(db_pool: asyncpg.Pool) -> None:
    # split_migration_sql, not raw .read_text(): the file carries a
    # `-- === ROLLBACK ===` section (CLAUDE.md's own documented scar —
    # "Migration Runner Was Executing ROLLBACK Section In-Transaction",
    # 2026-04-19) whose DROP statements would otherwise execute in the same
    # implicit batch as the CREATE statements and silently undo them.
    forward_sql, _ = split_migration_sql(_MIGRATION_281_PATH.read_text())
    async with db_pool.acquire() as conn:
        await conn.execute(_TEARDOWN_281_SQL)  # defensive, in case a prior run left it
        await conn.execute(forward_sql)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(_TEARDOWN_281_SQL)


class TestSuccessPath:
    async def test_returns_202_with_real_uuid_and_persists_the_row(
        self,
        db_pool: asyncpg.Pool,
        consultant_requests_schema: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)  # keep notify a no-op
        app = _build_app(db_pool)
        client_id = str(uuid.uuid4())
        product_version_id = str(uuid.uuid4())
        body = _valid_body(
            client_id=client_id,
            tier="T3",
            origin_screen="checkout",
            product_version_id=product_version_id,
            locale="id",
        )

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 202
        payload = response.json()
        # No `accepted` field (team-lead review finding: it could only ever
        # be True, which is a field that means nothing — the 202 status
        # already carries acceptance). Assert its ABSENCE, not its value —
        # a stray `accepted` key surviving a future edit would be exactly
        # the dead-field regression this removal was for.
        assert set(payload.keys()) == {"request_id"}
        request_id = uuid.UUID(payload["request_id"])  # raises if not a real UUID

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.visa_oracle_consultant_requests WHERE id = $1",
                request_id,
            )
        assert row is not None
        assert str(row["evaluation_id"]) == body["evaluation_id"]
        assert str(row["client_id"]) == client_id
        assert row["origin_screen"] == "checkout"
        assert row["tier"] == "T3"
        assert str(row["product_version_id"]) == product_version_id
        assert row["locale"] == "id"

    async def test_anonymous_pre_verdict_case_client_id_and_product_version_id_null(
        self,
        db_pool: asyncpg.Pool,
        consultant_requests_schema: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        app = _build_app(db_pool)
        body = _valid_body(origin_screen="wizard", tier="T3")  # no client_id, no product_version_id

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 202
        request_id = uuid.UUID(response.json()["request_id"])
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT client_id, product_version_id FROM public.visa_oracle_consultant_requests "
                "WHERE id = $1",
                request_id,
            )
        assert row["client_id"] is None
        assert row["product_version_id"] is None


# ---------------------------------------------------------------------------
# Rejected at the API boundary — no DB needed (fails before persistence)
# ---------------------------------------------------------------------------


class _UntouchedPool:
    """Fails the test if the router ever tries to acquire a connection —
    proves a rejected request never reaches the persistence step."""

    def acquire(self) -> None:
        raise AssertionError("db_pool must not be touched when the body is rejected")


class TestRejectedAtApiBoundary:
    async def test_missing_required_field_is_422(self) -> None:
        app = _build_app(_UntouchedPool())
        body = _valid_body()
        del body["origin_screen"]

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 422

    async def test_invalid_enum_value_is_422(self) -> None:
        app = _build_app(_UntouchedPool())
        body = _valid_body(origin_screen="bogus_screen")

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 422

    @pytest.mark.parametrize("pii_key", ["phone", "email", "full_name", "whatsapp"])
    async def test_pii_shaped_extra_key_is_rejected_422_at_schema_layer(self, pii_key: str) -> None:
        """The body model's own ``extra="forbid"`` blocks a PII-shaped key
        before C3's dedicated Law 2 guard would ever run — see module
        docstring for why this is 422, not the 400 the original brief
        assumed."""

        app = _build_app(_UntouchedPool())
        body = _valid_body(**{pii_key: "smuggled-value"})

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 422

    async def test_requested_at_cannot_be_client_supplied(self) -> None:
        """C3's ``requested_at`` is server-stamped; the body schema has no
        such field, so attempting to supply one is just another unknown-key
        422 — proving a client cannot forge the audit timestamp."""

        app = _build_app(_UntouchedPool())
        body = _valid_body(requested_at="2020-01-01T00:00:00Z")

        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=body)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Persistence failure -> 500, and notify is never reached
# ---------------------------------------------------------------------------


class TestPersistenceFailure:
    async def test_db_failure_returns_500_and_notify_is_never_called(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notify_calls: list[object] = []

        async def _recording_notify(event: object, request_id: object) -> None:
            notify_calls.append((event, request_id))

        monkeypatch.setattr(
            consultant_assignment_service, "notify_consultant_assignment_request", _recording_notify
        )
        monkeypatch.setattr(
            visa_oracle_consultant, "notify_consultant_assignment_request", _recording_notify
        )

        class _FailingPool:
            def acquire(self) -> None:
                raise ConnectionError("simulated DB outage")

        app = _build_app(_FailingPool())
        async with _client(app) as ac:
            response = await ac.post("/api/visa-oracle/consultant-assignment", json=_valid_body())

        assert response.status_code == 500
        assert notify_calls == []
