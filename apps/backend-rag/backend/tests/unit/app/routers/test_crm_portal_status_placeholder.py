"""Guilt/innocence for crm_portal_integration.py::get_portal_status.

Two defects, one query, both measured live on 2026-09-10.

DEFECT 1 — `portal_access = true` was treated as portal access.
`PortalProfileService.ensure_portal_profile()` runs as a background task on
every client creation that carries an email, and inserts the row with
`portal_access = true` and PLACEHOLDER_PIN_HASH — a hash no PIN can ever match.
Measured on production: of 532 active client rows with `portal_access = true`,
**448 carry that placeholder and can never log in** (84%), and only 9 have ever
logged in at all. So this endpoint answered "has portal access" for 448 clients
who were never invited, and the workspace consequently showed "Portal active"
and HID the control that would have invited them. The invite path was therefore
unreachable for the common case: a client created with an email already on file.

DEFECT 2 — `SELECT tm.created_at as last_login` aliased the creation date to
the last-login field, so every "Last signed in ..." the CRM displayed was in
fact "record created on ...". Measured on the same client: the API returned
04:02:25 (created_at) while the real `last_login` was 04:03:00, 35 seconds
later.

These tests assert on the QUERY, because the whole behaviour lives in SQL: the
row is either filtered out by the database or it is not. The live behavioural
proof is recorded in the PR — client 5, carrying `portal_access = true` and the
placeholder, flipped from `has_portal_access: true` to `false`, while client 4,
carrying real bcrypt credentials, stayed `true` AND began reporting the real
`last_login` instead of `created_at`.

Reverting either line of the cure turns these red.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.routers.crm_portal_integration import get_portal_status
from backend.services.portal.portal_profile_service import PLACEHOLDER_PIN_HASH


class _RecordingConnection:
    """Captures every query and its bind parameters, returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> None:
        self.calls.append((query, args))
        return None

    async def fetchval(self, query: str, *args: Any) -> None:
        self.calls.append((query, args))
        return None


class _Acquire:
    def __init__(self, conn: _RecordingConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _RecordingConnection:
        return self._conn

    async def __aexit__(self, *_: object) -> None:
        return None


class _Pool:
    def __init__(self, conn: _RecordingConnection) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


async def _run_status(monkeypatch: pytest.MonkeyPatch) -> _RecordingConnection:
    conn = _RecordingConnection()

    async def _allow_access(*_: object, **__: object) -> tuple[bool, str | None]:
        return True, "consultant@balizero.com"

    monkeypatch.setattr(
        "backend.app.routers.crm_portal_integration.verify_client_access",
        _allow_access,
    )

    await get_portal_status(
        client_id=4,
        current_user={"email": "consultant@balizero.com", "role": "Consultant"},
        db_pool=_Pool(conn),  # type: ignore[arg-type]
    )
    return conn


def _portal_user_query(conn: _RecordingConnection) -> tuple[str, tuple[Any, ...]]:
    for query, args in conn.calls:
        if "team_members" in query:
            return query, args
    raise AssertionError(
        "no query against team_members was issued — the portal-user lookup "
        "was renamed or removed; update this test rather than deleting it.",
    )


@pytest.mark.asyncio
async def test_placeholder_account_is_excluded_from_portal_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: a provisioned-but-unusable account must not count as access."""
    conn = await _run_status(monkeypatch)
    query, args = _portal_user_query(conn)

    assert "pin_hash" in query, (
        "the portal-user lookup no longer filters on pin_hash, so the 448 "
        "production rows carrying PLACEHOLDER_PIN_HASH would read as "
        "'has portal access' again"
    )
    assert PLACEHOLDER_PIN_HASH in args, (
        "the placeholder hash must be passed as a bind PARAMETER and compared "
        "by equality — an entity test, not a substring of it (superscar #3)"
    )


@pytest.mark.asyncio
async def test_last_login_is_read_from_the_last_login_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: the creation date must never be dressed up as a sign-in."""
    conn = await _run_status(monkeypatch)
    query, _ = _portal_user_query(conn)

    assert "created_at as last_login" not in query.lower(), (
        "created_at is being aliased to last_login again — the CRM would "
        "report a sign-in date for a client who has never signed in"
    )
    assert "tm.last_login" in query


@pytest.mark.asyncio
async def test_pending_invitation_lookup_is_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE: the invitation branch must keep working unchanged."""
    conn = await _run_status(monkeypatch)

    invite_queries = [q for q, _ in conn.calls if "client_invitations" in q]
    assert invite_queries, "the pending-invitation lookup disappeared"
    invite_query = invite_queries[0]
    assert "used_at IS NULL" in invite_query
    assert "expires_at > NOW()" in invite_query


@pytest.mark.asyncio
async def test_access_check_still_runs_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE: RBAC must not have been bypassed while editing the query."""
    calls: list[int] = []

    async def _record_access(client_id: int, *_: object, **__: object):
        calls.append(client_id)
        return True, "consultant@balizero.com"

    monkeypatch.setattr(
        "backend.app.routers.crm_portal_integration.verify_client_access",
        _record_access,
    )
    conn = _RecordingConnection()
    await get_portal_status(
        client_id=7,
        current_user={"email": "consultant@balizero.com", "role": "Consultant"},
        db_pool=_Pool(conn),  # type: ignore[arg-type]
    )
    assert calls == [7]
