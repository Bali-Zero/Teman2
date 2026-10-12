"""Deleted documents stay out of the team's CRM document readers.

GO 24 Sep 2026 (Antonello), shape (b) chosen 1 Oct 2026:
- The admin document list (GET /api/crm/clients/{id}/documents), the OCR
  status poll, and the evidence dossier hide BOTH kinds of deletion:
  ``status = 'deleted'`` (written by the team route) and ``deleted_at``
  (written by the client's portal soft-delete, which never touches status).
- The client profile (GET /api/crm/clients/{id}/profile) hides only
  ``status = 'deleted'``. It keeps returning rows with ``deleted_at`` set,
  because that is what feeds the "Removed" pill and the 30-day restore window
  (portal audit finding F-02).
- ``client_visible = false`` is NOT a deletion: internal team documents must
  stay visible to the team. That is why the portal's
  ``document_visibility_clause()`` is not reused here.

Measured by Antonello on production (30 Sep, read-only, aggregate): 187
deleted documents were still returned by the admin readers — 168 through
``status = 'deleted'``, 19 through ``deleted_at``.

Two kinds of test:
1. Behaviour: the predicate runs against real rows in an in-memory SQLite
   table (COALESCE / IS NULL / <> have the same meaning there), two GUILT
   rows and two INNOCENCE rows, as the GO asked.
2. Wiring: each reader's executed SQL carries the predicate. The handlers
   forward every row unchanged, so the SQL text is the contract.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Rows: (id, status, deleted_at, client_visible)
_ROWS = [
    (1, "active", "2026-09-30 10:00:00", 1),  # GUILT: client removed it in the portal
    (2, "deleted", None, 1),  # GUILT: team route marked it deleted
    (3, "active", None, 0),  # INNOCENCE: internal doc, hidden from client only
    (4, "active", None, 1),  # INNOCENCE: ordinary live document
    (5, None, None, 1),  # INNOCENCE: legacy row with NULL status
]


def _visible_ids(predicate: str) -> set[int]:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE documents (id INTEGER, status TEXT, deleted_at TEXT, client_visible INTEGER)"
    )
    db.executemany("INSERT INTO documents VALUES (?, ?, ?, ?)", _ROWS)
    rows = db.execute(f"SELECT d.id FROM documents d WHERE {predicate}").fetchall()
    db.close()
    return {r[0] for r in rows}


def _visible_ids_unaliased(predicate: str) -> set[int]:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE documents (id INTEGER, status TEXT, deleted_at TEXT, client_visible INTEGER)"
    )
    db.executemany("INSERT INTO documents VALUES (?, ?, ?, ?)", _ROWS)
    rows = db.execute(f"SELECT id FROM documents WHERE {predicate}").fetchall()
    db.close()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# 1. Behaviour
# ---------------------------------------------------------------------------


def test_positive_control_table_holds_all_rows() -> None:
    assert _visible_ids("1 = 1") == {1, 2, 3, 4, 5}


def test_admin_list_predicate_hides_both_deletions_keeps_internal_docs() -> None:
    from backend.services.crm.admin_document_visibility import admin_document_not_deleted_clause

    visible = _visible_ids(admin_document_not_deleted_clause("d"))
    assert 1 not in visible, "GUILT: client-deleted (deleted_at) must be hidden"
    assert 2 not in visible, "GUILT: status='deleted' must be hidden"
    assert 3 in visible, "INNOCENCE: client_visible=false stays visible to the team"
    assert 4 in visible, "INNOCENCE: live document stays visible"
    assert 5 in visible, "INNOCENCE: NULL status is not 'deleted'"


def test_admin_list_predicate_works_unaliased() -> None:
    from backend.services.crm.admin_document_visibility import admin_document_not_deleted_clause

    assert _visible_ids_unaliased(admin_document_not_deleted_clause()) == {3, 4, 5}


def test_profile_predicate_keeps_client_removed_rows_for_restore_window() -> None:
    from backend.services.crm.admin_document_visibility import (
        admin_document_not_team_deleted_clause,
    )

    visible = _visible_ids(admin_document_not_team_deleted_clause("d"))
    assert 1 in visible, "F-02: profile must still return the deleted_at row (Removed pill)"
    assert 2 not in visible, "GUILT: status='deleted' must be hidden in the profile too"
    assert visible == {1, 3, 4, 5}


# ---------------------------------------------------------------------------
# 2. Wiring — the SQL each reader actually executes
# ---------------------------------------------------------------------------

_HIDE_STATUS = "COALESCE(d.status, '') <> 'deleted'"
_HIDE_DELETED_AT = "d.deleted_at IS NULL"


def _pool_with_conn(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool


_ADMIN = {"id": "u1", "email": "zero@balizero.com", "role": "admin", "full_name": "A"}


@pytest.mark.asyncio
@pytest.mark.parametrize("include_archived", [False, True])
async def test_document_list_sql_hides_both_deletions(include_archived: bool) -> None:
    from backend.app.routers.crm_enhanced_documents import get_client_documents

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()):
        await get_client_documents(
            client_id=1,
            category=None,
            include_archived=include_archived,
            pool=_pool_with_conn(conn),
            current_user=_ADMIN,
        )
    sql = conn.fetch.await_args.args[0]
    assert _HIDE_STATUS in sql
    assert _HIDE_DELETED_AT in sql


@pytest.mark.asyncio
async def test_ocr_status_sql_hides_both_deletions() -> None:
    from backend.app.routers.crm_enhanced_documents import get_client_ocr_status

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()):
        await get_client_ocr_status(client_id=1, pool=_pool_with_conn(conn), current_user=_ADMIN)
    sql = conn.fetch.await_args.args[0]
    assert "COALESCE(status, '') <> 'deleted'" in sql
    assert "deleted_at IS NULL" in sql


def test_evidence_dossier_sql_hides_both_deletions() -> None:
    from backend.services.crm.evidence_dossier import _DOCUMENT_SQL

    assert "COALESCE(status, '') <> 'deleted'" in _DOCUMENT_SQL
    assert "deleted_at IS NULL" in _DOCUMENT_SQL


@pytest.mark.asyncio
async def test_profile_sql_hides_status_deleted_but_keeps_deleted_at_rows() -> None:
    from backend.app.routers.crm_enhanced import get_client_profile

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={"id": 1, "full_name": "T", "status": "active", "custom_fields": None}
    )
    conn.fetch = AsyncMock(return_value=[])
    with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
        await get_client_profile(client_id=1, pool=_pool_with_conn(conn), current_user=_ADMIN)
    doc_sql = [c.args[0] for c in conn.fetch.await_args_list if "FROM documents d" in c.args[0]]
    assert len(doc_sql) == 1
    assert _HIDE_STATUS in doc_sql[0]
    # F-02: the profile still projects and returns client-removed rows.
    assert "d.deleted_at" in doc_sql[0]
    assert _HIDE_DELETED_AT not in doc_sql[0]
