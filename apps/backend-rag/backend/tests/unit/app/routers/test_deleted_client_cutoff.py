"""A soft-deleted CRM client must not reach the portal — front door included.

Portal↔CRM bridge audit F4 (2026-09-11). Before this, the cutoff was
partial: `auth.py`'s login hit `team_members` alone with no join to
`clients`, so a client whose CRM record carried `deleted_at` — but whose
`team_members` row was still active with a real PIN — signed in
successfully. Most portal endpoints then 404'd on first use (the "BUG C"
fixes), but `get_messages` filtered nothing, so the archived client's whole
message history stayed readable.

Narrowing portal access for archived clients is a business decision reserved
to the owner (see `test_deleted_at_guard_registry.py`'s docstring). It was
taken deliberately, as item 8 of the owner's ordered remediation list, and
`DELETED_AT_GUARD_REGISTRY` records it in the same PR.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers import auth
from backend.services.portal.portal_service import PortalService


def _login_sql() -> str:
    """The login query, with comment lines stripped.

    The cure's own comment quotes what it replaced, and a substring test over
    raw source would convict the explanation (superscar #3, guard-over-match).
    """
    return "\n".join(
        line
        for line in inspect.getsource(auth.login).splitlines()
        if not line.lstrip().startswith("#")
    )


def test_login_joins_clients_and_excludes_soft_deleted_ones() -> None:
    """Guilt-proof: drop the join or the predicate and this fails."""
    sql = _login_sql()

    assert "LEFT JOIN clients c ON c.id = tm.linked_client_id" in sql
    assert "c.deleted_at IS NULL" in sql


def test_login_still_admits_staff_who_have_no_client_row() -> None:
    """The gate must not lock out staff.

    Staff `team_members` rows carry `linked_client_id IS NULL`, so a plain
    `c.deleted_at IS NULL` on a LEFT JOIN would evaluate NULL and exclude
    every one of them. The `linked_client_id IS NULL OR` arm is what keeps
    them in — remove it and this fails.
    """
    sql = _login_sql()

    assert "tm.linked_client_id IS NULL OR c.deleted_at IS NULL" in sql


class _Ctx:
    async def __aenter__(self) -> object:
        return None

    async def __aexit__(self, *_a: object) -> None:
        return None


def _service(client_row: object) -> tuple[PortalService, AsyncMock]:
    conn = AsyncMock()
    conn.fetchrow.return_value = client_row
    conn.transaction = MagicMock(return_value=_Ctx())
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return PortalService(pool), conn


@pytest.mark.asyncio
async def test_get_messages_refuses_a_soft_deleted_client() -> None:
    """The one read that never filtered.

    The router's `ValueError` catch was written for exactly this and carried
    a comment saying it was unreachable. It is reachable now, and answers 404
    like `get_dashboard` does.
    """
    service, conn = _service(client_row=None)

    with pytest.raises(ValueError, match="not found"):
        await service.get_messages(
            7,
            current_user={"client_id": 7, "email": "client@example.test"},
        )

    # The guard ran BEFORE any message was read.
    conn.fetch.assert_not_awaited()
    guard_sql = conn.fetchrow.call_args.args[0]
    assert "FROM clients" in guard_sql
    assert "deleted_at IS NULL" in guard_sql


@pytest.mark.asyncio
async def test_get_messages_still_serves_a_live_client() -> None:
    """INNOCENCE half: the guard must not refuse everyone.

    Without this, `raise ValueError` unconditionally would pass the test
    above — the guilt proof alone is not a discriminator.
    """
    service, conn = _service(client_row={"id": 7})
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0

    result = await service.get_messages(
        7,
        current_user={"client_id": 7, "email": "client@example.test"},
    )

    conn.fetch.assert_awaited()
    assert result["messages"] == []
