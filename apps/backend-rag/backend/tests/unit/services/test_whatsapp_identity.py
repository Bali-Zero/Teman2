"""Unit tests for the WhatsApp sender identity resolver."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from backend.services.whatsapp_identity import normalize_phone, resolve_sender_identity


class _FakeConn:
    def __init__(self, row: dict[str, Any] | None = None, error: Exception | None = None):
        self._row = row
        self._error = error
        self.last_args: tuple[Any, ...] | None = None

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.last_args = args
        if self._error is not None:
            raise self._error
        return self._row


class _FakeAcquire:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakePool:
    def __init__(self, row: dict[str, Any] | None = None, error: Exception | None = None):
        self.conn = _FakeConn(row=row, error=error)

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.conn)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("WHATSAPP_OWNER_NUMBERS", raising=False)
    monkeypatch.delenv("WHATSAPP_TEAM_NUMBERS", raising=False)


class TestNormalizePhone:
    def test_strips_punctuation_and_country_code(self):
        assert normalize_phone("+62 821-345-9999") == "8213459999"
        assert normalize_phone("628213459999") == "8213459999"
        assert normalize_phone("08213459999") == "8213459999"

    def test_empty_inputs(self):
        assert normalize_phone(None) is None
        assert normalize_phone("") is None
        assert normalize_phone("abc") is None


class TestResolveSenderIdentity:
    @pytest.mark.asyncio
    async def test_owner_default_number_all_formats(self):
        for raw in ("6282230102328", "+62 822-3010-2328", "082230102328"):
            identity = await resolve_sender_identity(raw, None)
            assert identity == {"role": "owner"}, raw

    @pytest.mark.asyncio
    async def test_owner_env_override(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_OWNER_NUMBERS", "62811000111, 62811000222")
        assert (await resolve_sender_identity("+62 811-000-222", None))["role"] == "owner"

    @pytest.mark.asyncio
    async def test_team_member_resolved_with_name(self, monkeypatch):
        monkeypatch.setenv(
            "WHATSAPP_TEAM_NUMBERS", "+628213454725:Adit,628213454723:Sahira"
        )
        identity = await resolve_sender_identity("628213454723", None)
        assert identity == {"role": "team", "team_member": "Sahira"}

    @pytest.mark.asyncio
    async def test_owner_wins_over_team(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEAM_NUMBERS", "6282230102328:NotZero")
        assert (await resolve_sender_identity("6282230102328", None))["role"] == "owner"

    @pytest.mark.asyncio
    async def test_client_lookup_hit(self):
        pool = _FakePool(row={"id": 42, "full_name": "Marta Reyes", "status": "active"})
        identity = await resolve_sender_identity("+62 813-555-0001", pool)
        assert identity == {
            "role": "client",
            "client_id": 42,
            "client_name": "Marta Reyes",
            "client_status": "active",
        }
        # The query receives the bare national digits.
        assert pool.conn.last_args == ("8135550001",)

    @pytest.mark.asyncio
    async def test_client_lookup_miss_is_unknown(self):
        identity = await resolve_sender_identity("+62 813-555-0002", _FakePool(row=None))
        assert identity == {"role": "unknown"}

    @pytest.mark.asyncio
    async def test_db_error_fails_safe_to_unknown(self):
        pool = _FakePool(error=asyncpg.PostgresError("boom"))
        assert (await resolve_sender_identity("+62 813-555-0003", pool)) == {
            "role": "unknown"
        }

    @pytest.mark.asyncio
    async def test_no_pool_no_match_is_unknown(self):
        assert (await resolve_sender_identity("+62 813-555-0004", None)) == {
            "role": "unknown"
        }

    @pytest.mark.asyncio
    async def test_empty_phone_is_unknown(self):
        assert (await resolve_sender_identity(None, _FakePool())) == {"role": "unknown"}
