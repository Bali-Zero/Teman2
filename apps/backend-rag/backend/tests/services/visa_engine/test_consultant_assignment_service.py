"""Guilt/innocence tests for the C3 wiring's persistence + notify half.

V3/unit-2 deliverable. Red-before-green: every test here failed with
``ModuleNotFoundError`` before ``consultant_assignment_service.py`` and
migration 281 existed. The append-only guard and the notify-failure-does-
not-block invariant are mutation-tested below (disable the mechanism,
confirm the SPECIFIC test that should catch it does, re-enable) — same
discipline as ``test_consultant_assignment.py``'s PII guard.

DB-integration tier only (no unit tier needed — the service has no branchy
logic worth isolating from the real INSERT/trigger behavior it exists to
prove).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.visa_engine.consultant_assignment import (
    ConsultantAssignmentEvent,
    EventLocale,
    OriginScreen,
    ServiceTier,
)
from backend.services.visa_engine.consultant_assignment_service import (
    notify_consultant_assignment_request,
    record_consultant_assignment_request,
)

pytestmark = pytest.mark.asyncio

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)
_MIGRATION_281_PATH = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "281_visa_oracle_consultant_requests.sql"
)
_TEARDOWN_281_SQL = """
DROP TRIGGER IF EXISTS trg_guard_visa_oracle_consultant_requests_append_only
    ON public.visa_oracle_consultant_requests;
DROP FUNCTION IF EXISTS public.guard_visa_oracle_consultant_requests_append_only();
DROP TABLE IF EXISTS public.visa_oracle_consultant_requests;
"""


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


def _event(**overrides: object) -> ConsultantAssignmentEvent:
    base: dict[str, object] = {
        "evaluation_id": uuid.uuid4(),
        "requested_at": datetime.now(timezone.utc),
        "origin_screen": OriginScreen.VERDICT,
        "tier": ServiceTier.T2,
        "locale": EventLocale.EN,
    }
    base.update(overrides)
    return ConsultantAssignmentEvent(**base)


# ---------------------------------------------------------------------------
# record_consultant_assignment_request — the durable write
# ---------------------------------------------------------------------------


class TestRecordConsultantAssignmentRequest:
    async def test_persists_all_seven_fields_round_trip(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        client_id = uuid.uuid4()
        product_version_id = uuid.uuid4()
        event = _event(
            client_id=client_id,
            tier=ServiceTier.T3,
            origin_screen=OriginScreen.CHECKOUT,
            product_version_id=product_version_id,
            locale=EventLocale.ID,
        )

        request_id = await record_consultant_assignment_request(event, db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.visa_oracle_consultant_requests WHERE id = $1",
                request_id,
            )
        assert row is not None
        assert row["evaluation_id"] == event.evaluation_id
        assert row["client_id"] == client_id
        assert row["origin_screen"] == "checkout"
        assert row["tier"] == "T3"
        assert row["product_version_id"] == product_version_id
        assert row["locale"] == "id"
        assert row["requested_at"] == event.requested_at

    async def test_client_id_and_product_version_id_persist_as_null(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        event = _event()  # both left None — the anonymous, pre-verdict case
        request_id = await record_consultant_assignment_request(event, db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT client_id, product_version_id FROM public.visa_oracle_consultant_requests "
                "WHERE id = $1",
                request_id,
            )
        assert row["client_id"] is None
        assert row["product_version_id"] is None

    async def test_two_requests_get_distinct_ids(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        first = await record_consultant_assignment_request(_event(), db_pool)
        second = await record_consultant_assignment_request(_event(), db_pool)
        assert first != second


# ---------------------------------------------------------------------------
# Append-only guard — guilt AND innocence, mutation-tested
# ---------------------------------------------------------------------------


class TestAppendOnlyGuard:
    async def test_update_is_rejected(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        request_id = await record_consultant_assignment_request(_event(), db_pool)
        async with db_pool.acquire() as conn:
            with pytest.raises(asyncpg.RaiseError, match="append-only"):
                await conn.execute(
                    "UPDATE public.visa_oracle_consultant_requests SET tier = 'T1' WHERE id = $1",
                    request_id,
                )

    async def test_delete_is_rejected(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        request_id = await record_consultant_assignment_request(_event(), db_pool)
        async with db_pool.acquire() as conn:
            with pytest.raises(asyncpg.RaiseError, match="append-only"):
                await conn.execute(
                    "DELETE FROM public.visa_oracle_consultant_requests WHERE id = $1",
                    request_id,
                )

    async def test_insert_still_works_guard_is_not_over_broad(
        self, db_pool: asyncpg.Pool, consultant_requests_schema: None
    ) -> None:
        """Innocence half: the guard is BEFORE UPDATE OR DELETE only — a
        fresh INSERT (the table's one legitimate operation) must never be
        caught by it."""

        request_id = await record_consultant_assignment_request(_event(), db_pool)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM public.visa_oracle_consultant_requests WHERE id = $1",
                request_id,
            )
        assert row is not None


# ---------------------------------------------------------------------------
# notify_consultant_assignment_request — best-effort, never raises
# ---------------------------------------------------------------------------


class TestNotifyConsultantAssignmentRequest:
    async def test_no_token_configured_is_a_silent_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Not-raising alone would also be true of a version that tried to
        send and silently ate a real failure — assert the SPECIFIC early-exit
        path: no HTTP client is even constructed when unconfigured."""

        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        client_constructed = False

        class _AssertNeverConstructedClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal client_constructed
                client_constructed = True

        monkeypatch.setattr(httpx, "AsyncClient", _AssertNeverConstructedClient)

        await notify_consultant_assignment_request(_event(), uuid.uuid4())

        assert client_constructed is False

    async def test_http_failure_is_swallowed_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Not-raising alone doesn't distinguish 'caught and logged' from
        'the whole function silently became a no-op' (the same shape as
        the guard mutation-test earlier in this file) — assert the specific
        warning fires, naming the failure, not just that nothing exploded."""

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-for-test")

        class _FailingClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def __aenter__(self) -> _FailingClient:
                return self

            async def __aexit__(self, *exc_info: object) -> None:
                return None

            async def post(self, *args: object, **kwargs: object) -> httpx.Response:
                raise httpx.ConnectError("simulated network failure")

        monkeypatch.setattr(httpx, "AsyncClient", _FailingClient)

        request_id = uuid.uuid4()
        with caplog.at_level(
            "WARNING", logger="backend.services.visa_engine.consultant_assignment_service"
        ):
            # Must not raise — this is the whole point of "best-effort".
            await notify_consultant_assignment_request(_event(), request_id)

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        assert "swallowed" in warnings[0].message
        assert str(request_id) in warnings[0].message
        assert "simulated network failure" in warnings[0].message

    async def test_configured_and_successful_posts_to_telegram_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-for-test")
        monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "12345")
        captured: dict[str, object] = {}

        class _RecordingClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def __aenter__(self) -> _RecordingClient:
                return self

            async def __aexit__(self, *exc_info: object) -> None:
                return None

            async def post(self, url: str, data: dict[str, object]) -> httpx.Response:
                captured["url"] = url
                captured["data"] = data
                return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx, "AsyncClient", _RecordingClient)

        request_id = uuid.uuid4()
        event = _event(tier=ServiceTier.T3)
        await notify_consultant_assignment_request(event, request_id)

        assert "fake-token-for-test" in captured["url"]
        assert captured["data"]["chat_id"] == "12345"
        text = captured["data"]["text"]
        assert str(request_id) in text
        assert "T3" in text
        assert str(event.evaluation_id) in text
        # Law 2: nothing PII-shaped can appear because the event itself
        # cannot carry it — this is the closest a notify test gets to that
        # invariant without duplicating test_consultant_assignment.py.
        assert "@" not in text
