-- 232_accounting_asya.sql
--
-- Accounting feature for Asya (the agency accountant). Adds the cash-control
-- workflow organs that don't exist yet, on top of the live invoice/practice
-- machinery. Design vetted by a 3-LLM adversarial panel (Gemini + DeepSeek +
-- Codex, unanimous GO-WITH-CHANGES) and Zero's decisions (2026-06-25):
--   * SINGLE flat money-log, NOT double-entry (panel: "accounting cosplay" for 1 accountant)
--   * NO cash_advances table -- PNBP is paid AFTER the client pays, so it is a
--     cost component of the practice price, never a client receivable (Zero #5)
--   * NO PPN columns load-bearing -- Bali Zero does not invoice 11% VAT (Zero #3);
--     a dormant pph_withheld field stays for B2B PPh23 deltas during reconciliation
--   * weekly_cashout mirrors Asya's real Google Sheet "Weekly Cashout 2026"
--     columns: NAME/PROCESS/PNBP/URGENT/RPTKA-IMTA/MARGIN BS/FINAL PRICE/NOTE
--   * reconciliation_log = immutable audit per payment confirm (Codex)
--
-- superscar guardrails: #2 (4-state reconciled_status, nothing vanishes silently),
-- #9 (payment_status stays the CRM-side truth; this schema is additive, the
-- reconciliation SERVICE is the single writer via the existing PATCH path).
--
-- FK targets verified on disk: clients(id) INT, practices(id) INT,
-- invoices(practice_id) INT, team_members(id) VARCHAR.

-- ============================================================================
-- 1. bank_statements -- one uploaded statement file (CSV/PDF) per import
-- ============================================================================
CREATE TABLE IF NOT EXISTS bank_statements (
    id                  BIGSERIAL PRIMARY KEY,
    bank_code           TEXT NOT NULL DEFAULT 'cimb_niaga',
    account_label       TEXT,
    uploaded_by         VARCHAR REFERENCES team_members(id) ON DELETE SET NULL,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_filename     TEXT,
    source_format       TEXT NOT NULL DEFAULT 'csv',
    period_start        DATE,
    period_end          DATE,
    opening_balance_idr BIGINT,
    closing_balance_idr BIGINT,
    parse_status        TEXT NOT NULL DEFAULT 'parsed',
    balance_check_ok    BOOLEAN,
    txn_count           INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT ck_bank_statements_format
        CHECK (source_format IN ('csv', 'xlsx', 'pdf', 'manual')),
    CONSTRAINT ck_bank_statements_parse_status
        CHECK (parse_status IN ('parsed', 'needs_review', 'failed'))
);
CREATE INDEX IF NOT EXISTS idx_bank_statements_uploaded_at
    ON bank_statements (uploaded_at DESC);

-- ============================================================================
-- 2. bank_transactions -- normalized rows parsed from a statement.
--    direction normalizes BCA's DB/CR flag and Mandiri/BRI's two columns.
--    4-state reconciled_status: nothing silently dropped (superscar #2).
-- ============================================================================
CREATE TABLE IF NOT EXISTS bank_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    statement_id        BIGINT NOT NULL REFERENCES bank_statements(id) ON DELETE CASCADE,
    txn_date            DATE NOT NULL,
    description         TEXT,
    amount_idr          BIGINT NOT NULL,
    direction           TEXT NOT NULL,
    running_balance_idr BIGINT,
    bank_account_id     TEXT,
    reconciled_status   TEXT NOT NULL DEFAULT 'unmatched',
    matched_practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    matched_invoice_id  BIGINT,
    raw_row             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_bank_txn_direction
        CHECK (direction IN ('credit', 'debit')),
    CONSTRAINT ck_bank_txn_reconciled_status
        CHECK (reconciled_status IN ('unmatched', 'matched', 'manual', 'ignored'))
);
CREATE INDEX IF NOT EXISTS idx_bank_txn_statement
    ON bank_transactions (statement_id);
CREATE INDEX IF NOT EXISTS idx_bank_txn_unmatched
    ON bank_transactions (txn_date DESC)
    WHERE reconciled_status = 'unmatched';
CREATE INDEX IF NOT EXISTS idx_bank_txn_matched_practice
    ON bank_transactions (matched_practice_id)
    WHERE matched_practice_id IS NOT NULL;

-- ============================================================================
-- 3. weekly_cashout -- THE single flat money-log (single-entry, cash-basis).
--    Mirrors Asya's "Weekly Cashout 2026" sheet. One row per money event.
--    For an invoice payment the price is decomposed like her sheet: pnbp +
--    urgent + rptka_imta are cost components; margin_idr is Bali Zero's margin;
--    final_price_idr is what the client paid. Generic out-flows (IT/SaaS subs,
--    office) are rows with type='expense'.
-- ============================================================================
CREATE TABLE IF NOT EXISTS weekly_cashout (
    id                  BIGSERIAL PRIMARY KEY,
    movement_date       DATE NOT NULL,
    week_label          TEXT,
    direction           TEXT NOT NULL,
    type                TEXT NOT NULL,
    amount_idr          BIGINT NOT NULL,
    pnbp_idr            BIGINT NOT NULL DEFAULT 0,
    urgent_idr          BIGINT NOT NULL DEFAULT 0,
    rptka_imta_idr      BIGINT NOT NULL DEFAULT 0,
    margin_idr          BIGINT NOT NULL DEFAULT 0,
    final_price_idr     BIGINT NOT NULL DEFAULT 0,
    original_currency   TEXT NOT NULL DEFAULT 'IDR',
    original_amount     NUMERIC(16, 2),
    fx_rate             NUMERIC(14, 6),
    fx_date             DATE,
    pph_withheld_idr    BIGINT NOT NULL DEFAULT 0,
    bank_fee_idr        BIGINT NOT NULL DEFAULT 0,
    linked_practice_id  INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    linked_invoice_id   BIGINT,
    linked_bank_txn_id  BIGINT REFERENCES bank_transactions(id) ON DELETE SET NULL,
    category            TEXT,
    description         TEXT,
    counterparty        TEXT,
    payment_method      TEXT,
    receipt_drive_file_id TEXT,
    recorded_by         VARCHAR REFERENCES team_members(id) ON DELETE SET NULL,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    reversed_by_id      BIGINT REFERENCES weekly_cashout(id) ON DELETE SET NULL,
    CONSTRAINT ck_cashout_direction
        CHECK (direction IN ('in', 'out')),
    CONSTRAINT ck_cashout_type
        CHECK (type IN (
            'invoice_payment', 'expense', 'payroll', 'commission',
            'bank_fee', 'pnbp_payment', 'tax_payment', 'refund', 'manual'
        )),
    CONSTRAINT ck_cashout_payment_method
        CHECK (payment_method IS NULL OR payment_method IN ('cash', 'bank_transfer', 'card'))
);
CREATE INDEX IF NOT EXISTS idx_cashout_movement_date
    ON weekly_cashout (movement_date DESC);
CREATE INDEX IF NOT EXISTS idx_cashout_type
    ON weekly_cashout (type);
CREATE INDEX IF NOT EXISTS idx_cashout_practice
    ON weekly_cashout (linked_practice_id)
    WHERE linked_practice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cashout_week
    ON weekly_cashout (week_label);

-- ============================================================================
-- 4. reconciliation_log -- immutable audit trail per payment confirmation.
--    Un-reconcile appends a reversal row (reversal_of_id), never deletes.
-- ============================================================================
CREATE TABLE IF NOT EXISTS reconciliation_log (
    id                  BIGSERIAL PRIMARY KEY,
    bank_txn_id         BIGINT REFERENCES bank_transactions(id) ON DELETE SET NULL,
    invoice_ids         JSONB,
    practice_id         INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    cashout_id          BIGINT REFERENCES weekly_cashout(id) ON DELETE SET NULL,
    confirmed_by        VARCHAR REFERENCES team_members(id) ON DELETE SET NULL,
    confirmed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_before       TEXT,
    status_after        TEXT,
    amount_applied_idr  BIGINT,
    pph_delta_idr       BIGINT NOT NULL DEFAULT 0,
    bank_fee_delta_idr  BIGINT NOT NULL DEFAULT 0,
    reversal_of_id      BIGINT REFERENCES reconciliation_log(id) ON DELETE SET NULL,
    note                TEXT
);
CREATE INDEX IF NOT EXISTS idx_recon_log_practice
    ON reconciliation_log (practice_id);
CREATE INDEX IF NOT EXISTS idx_recon_log_confirmed_at
    ON reconciliation_log (confirmed_at DESC);

-- ============================================================================
-- 5. Extend invoices (thin -> reconciliation-ready). Idempotent ADD COLUMN.
--    NO PPN column (Zero #3). pph_expected_idr lets the matcher know a B2B
--    transfer arrives net of 2% PPh23 (so amount < gross is expected).
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'invoices') THEN
        ALTER TABLE invoices ADD COLUMN IF NOT EXISTS paid_date TIMESTAMPTZ;
        ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_method VARCHAR(30);
        ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(120);
        ALTER TABLE invoices ADD COLUMN IF NOT EXISTS paid_amount_idr BIGINT;
        ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pph_expected_idr BIGINT DEFAULT 0;
    END IF;
END $$;

-- ============================================================================
-- 6. Runtime grants to backend_rag_v2 (skipped in CI where role is absent).
-- ============================================================================
DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    rw_objects text[] := ARRAY[
        'public.bank_statements', 'public.bank_transactions',
        'public.weekly_cashout', 'public.reconciliation_log'
    ];
    seq_objects text[] := ARRAY[
        'public.bank_statements_id_seq', 'public.bank_transactions_id_seq',
        'public.weekly_cashout_id_seq', 'public.reconciliation_log_id_seq'
    ];
    object_name text;
    object_reg regclass;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RAISE NOTICE 'Migration 232: role % absent; skipping grants (CI/fresh schema).', runtime_role;
        RETURN;
    END IF;
    FOREACH object_name IN ARRAY rw_objects LOOP
        object_reg := to_regclass(object_name);
        IF object_reg IS NULL THEN CONTINUE; END IF;
        BEGIN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %s TO %I', object_reg, runtime_role);
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE WARNING 'manual grant required: GRANT DML ON % TO %', object_reg, runtime_role;
        END;
    END LOOP;
    FOREACH object_name IN ARRAY seq_objects LOOP
        object_reg := to_regclass(object_name);
        IF object_reg IS NULL THEN CONTINUE; END IF;
        BEGIN
            EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I', object_reg, runtime_role);
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE WARNING 'manual grant required: GRANT USAGE ON SEQUENCE % TO %', object_reg, runtime_role;
        END;
    END LOOP;
END $grant_block$;

-- === ROLLBACK ===
DO $$
BEGIN
    ALTER TABLE IF EXISTS invoices DROP COLUMN IF EXISTS paid_date;
    ALTER TABLE IF EXISTS invoices DROP COLUMN IF EXISTS payment_method;
    ALTER TABLE IF EXISTS invoices DROP COLUMN IF EXISTS payment_reference;
    ALTER TABLE IF EXISTS invoices DROP COLUMN IF EXISTS paid_amount_idr;
    ALTER TABLE IF EXISTS invoices DROP COLUMN IF EXISTS pph_expected_idr;
END $$;
DROP TABLE IF EXISTS reconciliation_log;
DROP TABLE IF EXISTS weekly_cashout;
DROP TABLE IF EXISTS bank_transactions;
DROP TABLE IF EXISTS bank_statements;
