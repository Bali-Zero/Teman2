-- ============================================================
-- 108_lkpm_receipts.sql
-- LKPM tanda terima (OSS receipts) child table
-- Date: 2026-04-15
--
-- Each LKPM report in lkpm_reports aggregates one PT's quarterly activity,
-- but OSS issues a separate "Tanda Terima" PDF per Nomor Kegiatan Usaha.
-- A single PT commonly has 3-5 receipts per quarter (one per KBLI).
-- lkpm_reports has only scalar oss_receipt_number / oss_receipt_file_url
-- columns, insufficient for the multi-KBLI case.
--
-- Non-derivable notes:
--   nomor_laporan (e.g. LK6804588) is the OSS laporan ID. Unique per PT+quarter
--     but distinct across kegiatan_usaha of the same PT. Enforced UNIQUE globally.
--   stage observed values: "KONSTRUKSI", "PRODUKSI". Free text.
--   oss_status observed values: "Terkirim", "Disetujui". Free text.
--   FK to lkpm_reports.id with ON DELETE CASCADE: if a draft report is deleted,
--     its receipts go with it.
--
-- Idempotent: all statements use IF NOT EXISTS. Safe re-apply on production
-- where the table already exists (created out-of-band by the ingest script
-- import_lkpm_q1_2026_receipts.py on 2026-04-15 before the migration manager
-- system was used).
-- ============================================================

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
);

CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_report
    ON lkpm_receipts(lkpm_report_id);

CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_kegiatan
    ON lkpm_receipts(nomor_kegiatan_usaha);

CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_status
    ON lkpm_receipts(oss_status);
