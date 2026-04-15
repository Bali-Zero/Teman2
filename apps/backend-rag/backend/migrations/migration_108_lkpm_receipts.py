"""
Migration 108: LKPM tanda terima (OSS receipts) table.

Each LKPM report in `lkpm_reports` aggregates one PT's quarterly activity, but
OSS issues a separate "Tanda Terima" PDF per Nomor Kegiatan Usaha. A single PT
commonly has 3–5 receipts per quarter (one per KBLI). `lkpm_reports` has only
scalar `oss_receipt_number` / `oss_receipt_file_url` columns — insufficient.

This migration adds `lkpm_receipts` as a child table, one row per OSS receipt.

Non-derivable from code:
- `nomor_laporan` (e.g. LK6804588) is the OSS laporan ID. Unique per PT+quarter
  but distinct across kegiatan_usaha of the same PT. Enforced UNIQUE globally.
- `stage` observed values: "KONSTRUKSI", "PRODUKSI". Free text column.
- `oss_status` observed values: "Terkirim", "Disetujui". Free text column.
- FK to lkpm_reports.id with ON DELETE CASCADE: if a draft report is deleted,
  its receipts go with it.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "108_lkpm_receipts"
DESCRIPTION = (
    "LKPM: lkpm_receipts child table (one row per OSS tanda terima / "
    "Nomor Kegiatan Usaha), FK to lkpm_reports.id"
)


async def check_if_applied(conn) -> bool:
    """Idempotency: consider applied when the lkpm_receipts table exists."""
    result = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'lkpm_receipts' AND table_schema = 'public'
        )
        """,
    )
    return bool(result)


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lkpm_receipts (
            id SERIAL PRIMARY KEY,
            lkpm_report_id INTEGER NOT NULL
                REFERENCES lkpm_reports(id) ON DELETE CASCADE,
            nomor_laporan TEXT NOT NULL,
            nomor_kegiatan_usaha TEXT NOT NULL,
            kbli_code VARCHAR(10),
            kegiatan_usaha_desc TEXT,
            stage TEXT,
            oss_status TEXT,
            lokasi TEXT,
            tanggal_diterima DATE,
            nama_perusahaan_oss TEXT,
            file_drive_id TEXT,
            file_drive_url TEXT,
            file_name TEXT,
            source TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by TEXT,
            CONSTRAINT uq_lkpm_receipts_nomor_laporan UNIQUE (nomor_laporan)
        )
        """,
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_report
            ON lkpm_receipts(lkpm_report_id)
        """,
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_kegiatan
            ON lkpm_receipts(nomor_kegiatan_usaha)
        """,
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_status
            ON lkpm_receipts(oss_status)
        """,
    )

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.warning(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS lkpm_receipts CASCADE")


if __name__ == "__main__":
    import asyncio
    import os

    import asyncpg

    async def main() -> None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise SystemExit("DATABASE_URL not set")
        conn = await asyncpg.connect(dsn, timeout=15)
        try:
            if await check_if_applied(conn):
                logger.info(f"Migration {MIGRATION_ID} already applied — skipping")
                return
            async with conn.transaction():
                await apply(conn)
        finally:
            await conn.close()

    asyncio.run(main())
