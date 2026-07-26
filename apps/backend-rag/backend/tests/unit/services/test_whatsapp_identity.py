"""Unit tests for the WhatsApp sender identity resolver."""

from __future__ import annotations

import re
from typing import Any

import asyncpg
import pytest

from backend.services.whatsapp_identity import normalize_phone, resolve_sender_identity


def _digits(raw: str | None) -> str | None:
    if not raw:
        return None
    stripped = re.sub(r"[^0-9]", "", raw)
    return stripped or None


class _FakeConn:
    """Fakes asyncpg's connection.fetchrow(), routed by table name.

    Re-implements (in Python) the same WHERE-clause semantics as the real
    SQL in whatsapp_identity.py — including the ``role <> 'client'``
    overload guard AND the blank/NULL-role hardening (adversarial review,
    2026-07-20: a NULL/whitespace-only role must NOT classify as team,
    same as ``role='client'`` does not) — so tests can exercise the guard
    without a live Postgres. ``calls`` records every fetchrow invocation
    (sql, args) so tests can assert on call count/order/args.
    """

    def __init__(
        self,
        team_members: list[dict[str, Any]] | None = None,
        clients: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ):
        self._team_members = team_members or []
        self._clients = clients or []
        self._error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.calls.append((sql, args))
        if self._error is not None:
            raise self._error

        norm = args[0]
        candidates = {norm, "62" + norm, "0" + norm}

        if "team_members" in sql:
            for row in self._team_members:
                role_norm = str(row.get("role") or "").strip().lower()
                if not role_norm:
                    continue  # blank/NULL-role hardening
                if role_norm == "client":
                    continue  # the overload guard
                if row.get("active") is False:
                    continue
                if _digits(row.get("whatsapp")) in candidates:
                    return {
                        "id": row["id"],
                        "display_name": row.get("full_name") or row.get("name"),
                        "email": row.get("email"),
                    }
            return None

        for row in self._clients:
            phone_hit = _digits(row.get("phone")) in candidates
            wa_hit = _digits(row.get("whatsapp")) in candidates
            if phone_hit or wa_hit:
                return {
                    "id": row["id"],
                    "full_name": row.get("full_name"),
                    "status": row.get("status"),
                }
        return None

    @property
    def last_args(self) -> tuple[Any, ...] | None:
        return self.calls[-1][1] if self.calls else None


class _FakeAcquire:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakePool:
    def __init__(
        self,
        team_members: list[dict[str, Any]] | None = None,
        clients: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ):
        self.conn = _FakeConn(team_members=team_members, clients=clients, error=error)

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
    async def test_env_team_precedes_db_lookup(self, monkeypatch):
        # A DB row exists for the same number too, but the env override
        # must win AND the DB must never even be consulted.
        monkeypatch.setenv("WHATSAPP_TEAM_NUMBERS", "628111000999:EnvName")
        pool = _FakePool(
            team_members=[
                {
                    "id": "tm-1",
                    "full_name": "DB Name",
                    "name": "DB Name",
                    "email": "db.name@balizero.com",
                    "role": "Tax Lead",
                    "whatsapp": "+62 811-100-0999",
                    "active": True,
                }
            ]
        )
        identity = await resolve_sender_identity("628111000999", pool)
        assert identity == {"role": "team", "team_member": "EnvName"}
        assert pool.conn.calls == []

    @pytest.mark.asyncio
    async def test_team_db_lookup_hit_with_email(self):
        pool = _FakePool(
            team_members=[
                {
                    "id": "tm-2",
                    "full_name": "Test Member Alpha",
                    "name": "Test Member Alpha",
                    "email": "alpha.tester@balizero.com",
                    "role": "Tax Lead",
                    "whatsapp": "+62 811-100-2000",
                    "active": True,
                }
            ]
        )
        identity = await resolve_sender_identity("+62 811-100-2000", pool)
        assert identity == {
            "role": "team",
            "team_member": "Test Member Alpha",
            "team_member_email": "alpha.tester@balizero.com",
        }

    @pytest.mark.asyncio
    async def test_team_db_lookup_excludes_client_role(self):
        """The overload guard: a team_members row with role='client' that
        happens to carry a matching whatsapp number must NEVER resolve as
        team — the 495-row portal-client overload on this table is exactly
        the privacy incident this guard exists to prevent."""
        pool = _FakePool(
            team_members=[
                {
                    "id": "tm-ghost",
                    "full_name": "Portal Ghost",
                    "name": "Portal Ghost",
                    "email": "ghost@example.com",
                    "role": "client",
                    "whatsapp": "+62 811-100-3000",
                    "active": True,
                }
            ],
            clients=[],
        )
        identity = await resolve_sender_identity("+62 811-100-3000", pool)
        assert identity == {"role": "unknown"}

    @pytest.mark.asyncio
    async def test_team_db_lookup_excludes_blank_role(self):
        """Adversarial-review hardening (2026-07-20): a NULL/whitespace-only
        role must NOT classify as team, same as role='client' does not.
        `<> 'client'` alone is fail-OPEN for a blank role — this is the gap
        Codex's cross-family review found. No real row is blank today
        (verified live), but the guard must not silently rely on that."""
        pool = _FakePool(
            team_members=[
                {
                    "id": "tm-blank",
                    "full_name": "Data-Quality Gap",
                    "name": "Data-Quality Gap",
                    "email": "gap@example.com",
                    "role": None,
                    "whatsapp": "+62 811-100-3500",
                    "active": True,
                },
                {
                    "id": "tm-whitespace",
                    "full_name": "Data-Quality Gap 2",
                    "name": "Data-Quality Gap 2",
                    "email": "gap2@example.com",
                    "role": "   ",
                    "whatsapp": "+62 811-100-3600",
                    "active": True,
                },
            ],
            clients=[],
        )
        identity_null = await resolve_sender_identity("+62 811-100-3500", pool)
        identity_whitespace = await resolve_sender_identity("+62 811-100-3600", pool)
        assert identity_null == {"role": "unknown"}
        assert identity_whitespace == {"role": "unknown"}

    @pytest.mark.asyncio
    async def test_team_db_lookup_excludes_inactive(self):
        pool = _FakePool(
            team_members=[
                {
                    "id": "tm-3",
                    "full_name": "Former Member",
                    "name": "Former Member",
                    "email": "former@balizero.com",
                    "role": "Consultant",
                    "whatsapp": "+62 811-100-4000",
                    "active": False,
                }
            ],
        )
        identity = await resolve_sender_identity("+62 811-100-4000", pool)
        assert identity == {"role": "unknown"}

    @pytest.mark.asyncio
    async def test_team_db_lookup_miss_falls_through_to_client(self):
        pool = _FakePool(
            team_members=[],
            clients=[{"id": 7, "full_name": "Some Client", "status": "active",
                       "phone": "+62 811-100-5000"}],
        )
        identity = await resolve_sender_identity("+62 811-100-5000", pool)
        assert identity == {
            "role": "client",
            "client_id": 7,
            "client_name": "Some Client",
            "client_status": "active",
        }

    @pytest.mark.asyncio
    async def test_client_lookup_hit(self):
        pool = _FakePool(
            clients=[
                {
                    "id": 42,
                    "full_name": "Marta Reyes",
                    "status": "active",
                    "phone": "+62 813-555-0001",
                }
            ]
        )
        identity = await resolve_sender_identity("+62 813-555-0001", pool)
        assert identity == {
            "role": "client",
            "client_id": 42,
            "client_name": "Marta Reyes",
            "client_status": "active",
        }
        # The client query receives the bare national digits.
        assert pool.conn.last_args == ("8135550001",)

    @pytest.mark.asyncio
    async def test_client_lookup_miss_is_unknown(self):
        identity = await resolve_sender_identity("+62 813-555-0002", _FakePool())
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
