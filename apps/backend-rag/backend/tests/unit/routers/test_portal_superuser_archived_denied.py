"""
Tests for get_current_client's SUPERUSER paths — an archived client cannot be
impersonated or self-viewed either (GARUDA VOA L4, 2026-08-25).

SCAR CONTEXT: `test_portal_archived_client_denied.py` (M1, 2026-08-23) fail-closed
the NORMAL client path when `clients.deleted_at` is set, but its own docstring
says plainly: "The superuser impersonation path (lines ~145-213) is deliberately
untouched by this change and is not exercised here." That gap is exactly the
kita<->my audit finding GARUDA VOA L4 was dispatched to cure before adding any
portal surface on top of it (`products/garuda-voa/LANES.md` L4 prerequisite):
`get_current_client` had two more raw `clients` lookups —

1. The superuser own-email fallback (`?as_client` absent): admin views their
   OWN linked client row if any exists, with no `deleted_at` filter at all.
2. The explicit `?as_client=<id>` impersonation branch: same missing filter.

Both meant an admin could keep impersonating (or self-viewing) a client Bali
Zero had already archived in kita — the exact "existence != participation"
class the 2026-08-19 crm-portal-handoff-sim research documented for this file
(`portal.py:157-213`, the `is_superuser` branch), just one layer deeper than
the self-view collision that research already named.

Fix: both raw SQL lookups now carry `AND deleted_at IS NULL`, reusing the
EXISTING "not found" branch each already had (422 for the own-email fallback,
404 for the explicit `as_client` branch) — no new HTTP shape, no new code
path, same posture the M1 fix already established for the normal client path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from backend.app.routers.portal import get_current_client

SUPERUSER = {
    "id": "admin-uuid-1",
    "email": "zero@balizero.com",
    "role": "admin",
}


def _mock_request(user: dict, query_params: dict | None = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = user
    request.query_params = query_params or {}
    request.url.path = "/api/portal/profile"
    return request


@pytest.fixture(autouse=True)
def _superuser_emails(monkeypatch):
    """Pin the superuser set so this test does not depend on live settings."""
    from backend.app.routers import portal as portal_mod

    monkeypatch.setattr(
        portal_mod, "_superuser_emails", lambda: frozenset({"zero@balizero.com"})
    )


class TestSuperuserOwnEmailFallbackDenied:
    """`?as_client` absent -> admin's own-email lookup against `clients`."""

    async def test_active_own_row_still_resolves(self, mock_db_pool):
        """INNOCENCE: a live (non-archived) own-linked client row still works —
        the new filter must not turn into a blanket denial."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {
            "id": 68,
            "email": "zero@balizero.com",
            "full_name": "Zero",
        }

        result = await get_current_client(_mock_request(SUPERUSER), db_pool=mock_db_pool)

        assert result["client_id"] == 68
        assert result["impersonating"] is False
        sql = conn.fetchrow.await_args.args[0]
        assert "deleted_at IS NULL" in sql

    async def test_archived_own_row_denied_422_not_leaked(self, mock_db_pool):
        """GUILT: the admin's linked client row is archived (deleted_at set) ->
        the query must filter it out and the existing 422 branch must fire, not
        a silent 200 with stale client data."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None  # filtered out by deleted_at IS NULL

        with pytest.raises(HTTPException) as exc_info:
            await get_current_client(_mock_request(SUPERUSER), db_pool=mock_db_pool)

        assert exc_info.value.status_code == 422
        sql = conn.fetchrow.await_args.args[0]
        assert "FROM clients" in sql
        assert "deleted_at IS NULL" in sql


class TestSuperuserExplicitAsClientDenied:
    """`?as_client=<id>` -> explicit impersonation lookup against `clients`."""

    async def test_active_target_still_resolves(self, mock_db_pool):
        """INNOCENCE: impersonating a live client still works."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.side_effect = [
            {"id": 99, "email": "client@example.com", "full_name": "Real Client"},
            None,  # _log_impersonation's audit INSERT (best-effort, ignored)
        ]

        result = await get_current_client(
            _mock_request(SUPERUSER, {"as_client": "99"}), db_pool=mock_db_pool
        )

        assert result["client_id"] == 99
        assert result["impersonating"] is True
        first_sql = conn.fetchrow.await_args_list[0].args[0]
        assert "deleted_at IS NULL" in first_sql

    async def test_archived_target_denied_404_not_impersonable(self, mock_db_pool):
        """GUILT: the target client is archived -> must 404 as "not found",
        identical to a client_id that never existed, and must NEVER reach the
        impersonation-audit INSERT (there is nothing to audit if nothing was
        authorized)."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None  # filtered out by deleted_at IS NULL

        with pytest.raises(HTTPException) as exc_info:
            await get_current_client(
                _mock_request(SUPERUSER, {"as_client": "99"}), db_pool=mock_db_pool
            )

        assert exc_info.value.status_code == 404
        # Only the client lookup ran — the audit-log INSERT never fired.
        conn.fetchrow.assert_awaited_once()
        sql = conn.fetchrow.await_args.args[0]
        assert "FROM clients" in sql
        assert "deleted_at IS NULL" in sql
        assert "WHERE id = $1" in sql
