-- Migration 043: Proper invoices table
-- Extracts invoice data out of practices.documents JSONB into a first-class table.
-- The service will write to BOTH during the transition period (dual-write), then
-- practices.documents['invoice'] will be dropped in a future cleanup migration.

CREATE TABLE IF NOT EXISTS invoices (
    id                   SERIAL PRIMARY KEY,
    practice_id          INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    client_id            INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Invoice identity
    invoice_number       TEXT UNIQUE,                        -- NULL for manual/legacy invoices
    invoice_source       TEXT NOT NULL DEFAULT 'manual',    -- 'local_pdf' | 'manual' | 'zoho'

    -- Financial snapshot at time of invoicing
    amount_idr           NUMERIC(15,2) NOT NULL DEFAULT 0,
    paid_amount_idr      NUMERIC(15,2) NOT NULL DEFAULT 0,

    -- Drive backup
    drive_file_id        TEXT,
    drive_web_link       TEXT,

    -- Delivery status
    email_sent_to_client BOOLEAN NOT NULL DEFAULT FALSE,
    accounting_notified  BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    generated_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One practice can have multiple invoice attempts (regenerate), but normally one active
CREATE INDEX IF NOT EXISTS idx_invoices_practice ON invoices(practice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_client   ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_number   ON invoices(invoice_number) WHERE invoice_number IS NOT NULL;

-- ── Backfill from practices.documents JSONB ──────────────────────────────────
-- Only insert practices that have invoice data and don't already exist in table.
INSERT INTO invoices (
    practice_id,
    client_id,
    invoice_number,
    invoice_source,
    amount_idr,
    paid_amount_idr,
    drive_file_id,
    drive_web_link,
    email_sent_to_client,
    accounting_notified,
    generated_at,
    created_at
)
SELECT
    p.id                                                             AS practice_id,
    p.client_id                                                      AS client_id,
    NULLIF(p.documents::json->'invoice'->>'invoice_number', '')     AS invoice_number,
    COALESCE(
        NULLIF(p.documents::json->'invoice'->>'source', ''),
        'manual'
    )                                                                AS invoice_source,
    COALESCE(p.quoted_price, 0)                                      AS amount_idr,
    COALESCE(p.paid_amount, 0)                                       AS paid_amount_idr,
    NULLIF(p.documents::json->'invoice'->>'invoice_drive_id', '')   AS drive_file_id,
    NULLIF(p.documents::json->'invoice'->>'invoice_drive_link', '') AS drive_web_link,
    COALESCE(
        (p.documents::json->'invoice'->>'email_sent')::boolean,
        FALSE
    )                                                                AS email_sent_to_client,
    COALESCE(
        (p.documents::json->'invoice'->>'accounting_notified')::boolean,
        FALSE
    )                                                                AS accounting_notified,
    CASE
        WHEN p.documents::json->'invoice'->>'invoice_generated_at' IS NOT NULL
        THEN (p.documents::json->'invoice'->>'invoice_generated_at')::timestamptz
        ELSE NULL
    END                                                              AS generated_at,
    NOW()                                                            AS created_at
FROM practices p
WHERE p.documents::text LIKE '%invoice%'
ON CONFLICT DO NOTHING;
