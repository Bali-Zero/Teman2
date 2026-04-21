"""
Integration tests for LkpmReadyPack.generate().

5 tests using mocked Drive + Brevo services:
  1. happy path (dry_run=False) returns drive_url + hashes.
  2. dry_run=True skips Drive + email, returns hashes + nulls.
  3. Drive upload failure → drive_url=None, email not sent (graceful).
  4. Email failure → email_sent_to=None (graceful).
  5. Incomplete report raises LkpmValidationError (422 equivalent).

All DB interaction uses a real asyncpg pool + per-test transaction rolled back.
Tables needed: clients, lkpm_reports, lkpm_receipts, lkpm_client_config.
If lkpm_receipts is missing the test creates it inline via conftest.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import asyncpg
from unittest.mock import AsyncMock, MagicMock

from backend.services.compliance.exceptions import LkpmValidationError
from backend.services.compliance.lkpm_ready_pack import LkpmReadyPack

pytestmark = pytest.mark.integration


# ── Helpers ───────────────────────────────────────────────────────────────


async def _ensure_lkpm_tables(conn: asyncpg.Connection) -> None:
    """Create minimal LKPM tables if they don't exist (test-env safety net)."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lkpm_reports (
            id                          SERIAL PRIMARY KEY,
            client_id                   INT NOT NULL,
            company_id                  INT,
            quarter                     TEXT NOT NULL,
            year                        INT NOT NULL,
            status                      TEXT NOT NULL DEFAULT 'draft',
            lkpm_assigned_to            TEXT,
            realized_equipment_domestic BIGINT DEFAULT 0,
            realized_equipment_import   BIGINT DEFAULT 0,
            realized_building_domestic  BIGINT DEFAULT 0,
            realized_building_import    BIGINT DEFAULT 0,
            realized_vehicle_domestic   BIGINT DEFAULT 0,
            realized_vehicle_import     BIGINT DEFAULT 0,
            realized_land               BIGINT DEFAULT 0,
            realized_working_capital    BIGINT DEFAULT 0,
            realized_other              BIGINT DEFAULT 0,
            oss_submitted               BOOLEAN NOT NULL DEFAULT FALSE,
            oss_receipt_number          TEXT,
            client_approved             BOOLEAN NOT NULL DEFAULT FALSE,
            validation_status           TEXT DEFAULT 'pending',
            validation_alerts           JSONB DEFAULT '[]',
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lkpm_receipts (
            id                  SERIAL PRIMARY KEY,
            lkpm_report_id      INT NOT NULL,
            kbli_code           TEXT,
            kegiatan_usaha_desc TEXT,
            oss_status          TEXT,
            stage               TEXT
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lkpm_client_config (
            id           SERIAL PRIMARY KEY,
            client_id    INT NOT NULL,
            company_id   INT,
            company_name TEXT,
            nib          TEXT,
            npwp         TEXT,
            kbli_codes   TEXT[] DEFAULT '{}',
            oss_username TEXT,
            oss_password TEXT,
            oss_creds_updated_at TIMESTAMPTZ,
            oss_creds_updated_by TEXT
        )
        """
    )


async def _insert_complete_report(
    conn: asyncpg.Connection, client_id: int, quarter: str = "Q1", year: int = 2026
) -> int:
    """Insert a complete lkpm_reports row and return its id."""
    row = await conn.fetchrow(
        """
        INSERT INTO lkpm_reports (
            client_id, quarter, year, status,
            realized_equipment_domestic, realized_working_capital
        ) VALUES ($1, $2, $3, 'draft', 100000000, 50000000)
        RETURNING id
        """,
        client_id,
        quarter,
        year,
    )
    return row["id"]


async def _insert_incomplete_report(
    conn: asyncpg.Connection, client_id: int, quarter: str = "Q2", year: int = 2026
) -> int:
    """Insert an lkpm_reports row with NULL realization fields."""
    row = await conn.fetchrow(
        """
        INSERT INTO lkpm_reports (
            client_id, quarter, year, status,
            realized_equipment_domestic
        ) VALUES ($1, $2, $3, 'draft', NULL)
        RETURNING id
        """,
        client_id,
        quarter,
        year,
    )
    return row["id"]


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def db_pool() -> asyncpg.Pool:
    import os
    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_dev"
    )
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture()
async def db_tx(db_pool: asyncpg.Pool):
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        await _ensure_lkpm_tables(conn)
        try:
            yield conn, db_pool
        finally:
            await tx.rollback()


@pytest_asyncio.fixture()
async def client_row(db_tx) -> dict:
    conn, _ = db_tx
    row = await conn.fetchrow(
        """
        INSERT INTO clients (full_name, email, google_drive_folder_id, created_at, updated_at)
        VALUES ($1, $2, $3, NOW(), NOW())
        RETURNING id, full_name, email, google_drive_folder_id
        """,
        "PT Test Pack",
        "testpack@example.com",
        "fake_folder_id_123",
    )
    return dict(row)


def _make_drive(success: bool = True) -> MagicMock:
    drive = MagicMock()
    if success:
        drive.upload_file_to_folder = AsyncMock(
            return_value={"download_url": "https://drive.google.com/file/d/XYZ/view"}
        )
    else:
        drive.upload_file_to_folder = AsyncMock(side_effect=RuntimeError("Drive unavailable"))
    return drive


def _make_brevo(success: bool = True) -> MagicMock:
    brevo = MagicMock()
    brevo.send = AsyncMock(return_value=success)
    return brevo


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_returns_hashes_and_drive_url(db_tx, client_row: dict) -> None:
    """generate() with real DB, mock Drive + Brevo returns drive_url + sha256 hashes."""
    conn, pool = db_tx
    report_id = await _insert_complete_report(conn, client_row["id"])

    drive = _make_drive(success=True)
    brevo = _make_brevo(success=True)

    pack = LkpmReadyPack.with_connection(conn, drive=drive, brevo=brevo)
    result = await pack.generate(
        client_id=client_row["id"],
        period="Q1 2026",
        send_email=True,
        dry_run=False,
    )

    assert result["pdf_sha256"] and len(result["pdf_sha256"]) == 64
    assert result["xlsx_sha256"] and len(result["xlsx_sha256"]) == 64
    assert result["drive_url"] is not None
    # Email: Brevo was called (client has email + drive_url set)
    assert result["email_sent_to"] == "testpack@example.com"
    assert isinstance(result["validation_warnings"], list)


@pytest.mark.asyncio
async def test_dry_run_skips_drive_and_email(db_tx, client_row: dict) -> None:
    """dry_run=True returns hashes but drive_url=None and email_sent_to=None."""
    conn, pool = db_tx
    await _insert_complete_report(conn, client_row["id"])

    drive = _make_drive(success=True)
    brevo = _make_brevo(success=True)

    pack = LkpmReadyPack.with_connection(conn, drive=drive, brevo=brevo)
    result = await pack.generate(
        client_id=client_row["id"],
        period="Q1 2026",
        send_email=True,
        dry_run=True,
    )

    assert result["drive_url"] is None
    assert result["email_sent_to"] is None
    assert len(result["pdf_sha256"]) == 64
    assert len(result["xlsx_sha256"]) == 64
    # Drive and Brevo must NOT have been called
    drive.upload_file_to_folder.assert_not_called()
    brevo.send.assert_not_called()


@pytest.mark.asyncio
async def test_drive_failure_graceful(db_tx, client_row: dict) -> None:
    """Drive upload failure → drive_url=None, email not sent (graceful degradation)."""
    conn, pool = db_tx
    await _insert_complete_report(conn, client_row["id"])

    drive = _make_drive(success=False)
    brevo = _make_brevo(success=True)

    pack = LkpmReadyPack.with_connection(conn, drive=drive, brevo=brevo)
    result = await pack.generate(
        client_id=client_row["id"],
        period="Q1 2026",
        send_email=True,
        dry_run=False,
    )

    # Drive failed → no URL → email should NOT have been sent
    assert result["drive_url"] is None
    assert result["email_sent_to"] is None
    # Hashes still present
    assert len(result["pdf_sha256"]) == 64


@pytest.mark.asyncio
async def test_email_failure_graceful(db_tx, client_row: dict) -> None:
    """Brevo failure → email_sent_to=None (graceful), drive_url still present."""
    conn, pool = db_tx
    await _insert_complete_report(conn, client_row["id"])

    drive = _make_drive(success=True)
    brevo = _make_brevo(success=False)

    pack = LkpmReadyPack.with_connection(conn, drive=drive, brevo=brevo)
    result = await pack.generate(
        client_id=client_row["id"],
        period="Q1 2026",
        send_email=True,
        dry_run=False,
    )

    assert result["drive_url"] is not None
    assert result["email_sent_to"] is None  # Brevo returned False
    assert len(result["pdf_sha256"]) == 64


@pytest.mark.asyncio
async def test_incomplete_report_raises_validation_error(db_tx, client_row: dict) -> None:
    """Incomplete report (NULL realization field) must raise LkpmValidationError."""
    conn, pool = db_tx
    await _insert_incomplete_report(conn, client_row["id"])

    pack = LkpmReadyPack.with_connection(conn, drive=None, brevo=None)
    with pytest.raises(LkpmValidationError):
        await pack.generate(
            client_id=client_row["id"],
            period="Q2 2026",
        )


@pytest.mark.asyncio
async def test_xlsx_output_is_well_formed(db_tx, client_row: dict) -> None:
    """xlsx_sha256 must be a 64-char lowercase hex string (valid SHA-256)."""
    conn, pool = db_tx
    await _insert_complete_report(conn, client_row["id"], quarter="Q1", year=2026)

    pack = LkpmReadyPack.with_connection(conn, drive=None, brevo=None)
    result = await pack.generate(
        client_id=client_row["id"],
        period="Q1 2026",
        send_email=False,
        dry_run=True,
    )

    xlsx_sha = result["xlsx_sha256"]
    assert len(xlsx_sha) == 64, f"Expected 64-char sha256, got {len(xlsx_sha)}"
    assert all(c in "0123456789abcdef" for c in xlsx_sha), (
        f"xlsx_sha256 contains non-hex characters: {xlsx_sha!r}"
    )
