"""Regression test for ``get_clients_from_db`` — the visa-expiry subquery
repointed from ``client_documents`` (never provisioned in prod) to
``documents`` (the live table, 2026-08-08).

Both live callers share this one function:
    - ``POST /api/notifications/check`` (router.py) — 500'd on every call
      (``UndefinedTableError``, ``client_documents`` doesn't exist in prod).
    - ``NotificationScheduler._daily_check`` (scheduler.py, APScheduler cron
      09:00 WITA, started at boot) — the same exception was swallowed by a
      bare ``except Exception`` in ``_daily_check``, so the daily visa/passport
      expiry sweep has silently generated zero alerts since this endpoint was
      introduced (cicatrix-superscar family #2, "Esiste ≠ Armato").

GUILT: the query text no longer references ``client_documents`` anywhere,
and does reference ``documents`` with the ``document_category='immigration'``
filter that makes the visa-expiry join meaningful.

INNOCENCE: a client row with no matching immigration document (LEFT JOIN
produces NULLs for ``expiry_date``/``document_type``) does not crash
``get_clients_from_db`` — the missing visa data is just absent on the
resulting ``ClientInfo``.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest

from backend.app.modules.notifications.router import get_clients_from_db


class _PoolCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return False


class _Pool:
    """Minimal asyncpg.Pool stand-in — no live DB, no network."""

    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _PoolCtx(self._conn)


def test_query_no_longer_references_client_documents() -> None:
    """GUILT: ``client_documents`` was never provisioned in prod — the
    subquery must not reference it anywhere in the function source."""
    source = inspect.getsource(get_clients_from_db)
    assert "client_documents" not in source, (
        "get_clients_from_db still references the never-provisioned "
        "client_documents table — every call raises asyncpg.UndefinedTableError"
    )
    assert "FROM documents" in source, (
        "get_clients_from_db must join against the live `documents` table "
        "for the visa-expiry subquery"
    )
    assert "document_category = 'immigration'" in source


@pytest.mark.asyncio
async def test_single_client_query_returns_expected_shape() -> None:
    """GUILT (behavioral): for a single client_id, the query executes against
    `documents` and the row shape maps cleanly onto ClientInfo."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 42,
            "email": "client@example.com",
            "full_name": "Test Client",
            "preferred_language": "en",
            "team_leader_email": "ari@balizero.com",
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": "X1234567",
            "visa_expiry": None,
            "visa_type": "C1",
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=42)

    assert len(clients) == 1
    assert clients[0].id == 42
    assert clients[0].visa_type == "C1"

    # The SQL actually sent must target `documents`, not `client_documents`.
    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "client_documents" not in sql_sent
    assert "FROM documents" in sql_sent
    mock_conn.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_clients_query_returns_expected_shape() -> None:
    """GUILT (behavioral): the no-client_id (all active clients) branch also
    targets `documents`."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=None)

    assert clients == []
    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "client_documents" not in sql_sent
    assert "FROM documents" in sql_sent


@pytest.mark.asyncio
async def test_client_with_no_immigration_documents_does_not_crash() -> None:
    """INNOCENCE: a client with zero matching rows in `documents` (LEFT JOIN
    miss) must not crash — visa_expiry/visa_type simply come back None."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 7,
            "email": "no-docs@example.com",
            "full_name": "No Docs Client",
            "preferred_language": "en",
            "team_leader_email": None,
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": None,
            "visa_expiry": None,
            "visa_type": None,
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=7)

    assert len(clients) == 1
    assert clients[0].visa_expiry is None
    assert clients[0].visa_type is None
