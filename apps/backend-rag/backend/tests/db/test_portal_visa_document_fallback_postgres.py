"""Real-Postgres tests for the documents-based visa fallback.

`PortalDashboardMixin._get_latest_visible_visa_document` and the
`get_visa_status` "documents" whitelist both filter through SQL predicates
(`document_visibility_clause()`, `LOWER(document_type) IN (...)`, the
kitas/kitap/visa/voa family match) that a mocked-connection unit test can
assert the SHAPE of but never actually PROVE — a fake connection runs a
typo'd `WHERE` clause exactly as happily as a correct one. Only a real
Postgres exercising the real predicate shows the defect these tests guard:
production stores `'MERP'` uppercase-only (measured 2026-09-21, zero
lowercase rows) and the exact-match whitelist silently dropped it; a
client-hidden or archived document must never leak into a portal response
regardless of how recent its expiry is.

Uses `db_tx` (see `conftest.py`): every insert lives inside one rolled-back
transaction, so nothing here is ever committed. Client name is synthetic,
never a real client's PII.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import asyncpg
import pytest

from backend.services.portal.portal_service import PortalService

pytestmark = pytest.mark.integration


class _SingleConnectionPool:
    """Every `acquire()` yields the same `db_tx` connection — rows written
    by the code under test are visible to the assertions and vanish at
    rollback. Copied from `test_email_audit_record_result_postgres.py`."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner) -> asyncpg.Connection:
                return conn

            async def __aexit__(self_inner, *exc: object) -> bool:
                return False

        return _Ctx()


async def _ensure_schema_current(conn: asyncpg.Connection) -> None:
    """The local `nuzantara_test` template predates three prod columns this
    fallback needs (`documents.issue_date`, `documents.ocr_extracted_data`,
    `practices.client_visible`).
    Patch them in — transaction-scoped DDL, invisible to every other
    session and gone the instant `db_tx` rolls back — instead of widening
    scope into a full migration-runner rebuild of the local template."""
    await conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS issue_date date")
    await conn.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_extracted_data jsonb",
    )
    await conn.execute(
        "ALTER TABLE practices ADD COLUMN IF NOT EXISTS client_visible boolean",
    )


async def _make_client(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow(
        "INSERT INTO clients (full_name) VALUES ('W-portal-visa-fallback test client') "
        "RETURNING id",
    )
    return row["id"]


async def _make_document(
    conn: asyncpg.Connection,
    *,
    client_id: int,
    document_type: str,
    expiry_date: date | None = None,
    client_visible: bool = True,
    deleted_at_now: bool = False,
    is_archived: bool = False,
    ocr_extracted_data: str | None = None,
) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO documents (
            client_id, document_type, file_name, client_visible,
            is_archived, expiry_date, deleted_at, ocr_extracted_data
        ) VALUES (
            $1, $2, 'test.pdf', $3,
            $4, $5, CASE WHEN $6 THEN NOW() ELSE NULL END, $7::jsonb
        )
        RETURNING id
        """,
        client_id,
        document_type,
        client_visible,
        is_archived,
        expiry_date,
        deleted_at_now,
        ocr_extracted_data,
    )
    return row["id"]


@pytest.mark.asyncio
async def test_fallback_query_skips_hidden_deleted_and_archived_documents(
    db_tx: asyncpg.Connection,
) -> None:
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    client_id = await _make_client(db_tx)
    today = date.today()

    # A non-visible document with the LATEST expiry — must NOT win over the
    # visible one below despite sorting first by date.
    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitas",
        expiry_date=today + timedelta(days=300),
        client_visible=False,
    )
    # A client-soft-deleted document, also with a later expiry than the
    # winner.
    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitas",
        expiry_date=today + timedelta(days=200),
        deleted_at_now=True,
    )
    # A team-archived document.
    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitas",
        expiry_date=today + timedelta(days=100),
        is_archived=True,
    )
    # The only VISIBLE, non-deleted, non-archived visa-family document.
    visible_id = await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitas",
        expiry_date=today + timedelta(days=30),
    )

    result = await service._get_latest_visible_visa_document(db_tx, client_id)

    assert result is not None
    assert result["id"] == visible_id


@pytest.mark.asyncio
async def test_fallback_query_ignores_non_visa_family_document_types(
    db_tx: asyncpg.Connection,
) -> None:
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    client_id = await _make_client(db_tx)

    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="passport",
        expiry_date=date.today() + timedelta(days=365),
    )

    result = await service._get_latest_visible_visa_document(db_tx, client_id)

    assert result is None


@pytest.mark.asyncio
async def test_fallback_query_reads_permit_number_and_sponsor_from_ocr(
    db_tx: asyncpg.Connection,
) -> None:
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    with_ocr = await _make_client(db_tx)
    scalar_ocr = await _make_client(db_tx)

    await _make_document(
        db_tx,
        client_id=with_ocr,
        document_type="visa",
        expiry_date=date.today() + timedelta(days=90),
        ocr_extracted_data=(
            '{"raw_response": {"visa_number": "TEST-PERMIT-0001", "sponsor": "PT Example Sponsor"}}'
        ),
    )
    # A non-object OCR payload must read as "no OCR", not break the query.
    await _make_document(
        db_tx,
        client_id=scalar_ocr,
        document_type="visa",
        expiry_date=date.today() + timedelta(days=90),
        ocr_extracted_data='"unparsed"',
    )

    row = await service._get_latest_visible_visa_document(db_tx, with_ocr)
    assert row["ocr_visa_number"] == "TEST-PERMIT-0001"
    assert row["ocr_sponsor"] == "PT Example Sponsor"

    row = await service._get_latest_visible_visa_document(db_tx, scalar_ocr)
    assert row["ocr_visa_number"] is None
    assert row["ocr_sponsor"] is None


@pytest.mark.asyncio
async def test_fallback_query_applies_30_day_grace_and_prefers_dated_over_undated(
    db_tx: asyncpg.Connection,
) -> None:
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    client_id = await _make_client(db_tx)
    today = date.today()

    # Expired 45 days ago -> outside the 30-day grace window, must lose.
    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="e_visa",
        expiry_date=today - timedelta(days=45),
    )
    # Expired 10 days ago -> inside the grace window, should win over both
    # the too-old dated doc AND the undated one below.
    winner_id = await _make_document(
        db_tx,
        client_id=client_id,
        document_type="e_visa",
        expiry_date=today - timedelta(days=10),
    )
    # No expiry at all -> only a fallback of last resort.
    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="voa",
        expiry_date=None,
    )

    result = await service._get_latest_visible_visa_document(db_tx, client_id)

    assert result is not None
    assert result["id"] == winner_id


@pytest.mark.asyncio
async def test_fallback_query_falls_back_to_undated_document_when_all_dated_ones_expired(
    db_tx: asyncpg.Connection,
) -> None:
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    client_id = await _make_client(db_tx)
    today = date.today()

    await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitap",
        expiry_date=today - timedelta(days=400),
    )
    undated_id = await _make_document(
        db_tx,
        client_id=client_id,
        document_type="kitap",
        expiry_date=None,
    )

    result = await service._get_latest_visible_visa_document(db_tx, client_id)

    assert result is not None
    assert result["id"] == undated_id


@pytest.mark.asyncio
async def test_get_visa_status_documents_list_matches_merp_case_insensitively(
    db_tx: asyncpg.Connection,
) -> None:
    """GUILT for the whitelist fix: 'MERP' uppercase (the ONLY casing
    production has ever stored, per prod measurement 2026-09-21) must
    appear in VisaInfo.documents, and be categorized "Immigration" not
    "Other"."""
    service = PortalService(_SingleConnectionPool(db_tx))  # type: ignore[arg-type]
    await _ensure_schema_current(db_tx)
    client_id = await _make_client(db_tx)

    await _make_document(db_tx, client_id=client_id, document_type="MERP")

    result = await service.get_visa_status(client_id, current_user={"client_id": client_id})

    doc_types = [d["type"] for d in result["documents"]]
    assert "MERP" in doc_types
    merp_doc = next(d for d in result["documents"] if d["type"] == "MERP")
    assert merp_doc["category"] == "Immigration"
