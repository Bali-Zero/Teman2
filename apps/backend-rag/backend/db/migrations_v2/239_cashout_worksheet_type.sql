-- 239_cashout_worksheet_type.sql
--
-- Adds the 'cashout_worksheet' value to weekly_cashout.type's CHECK constraint.
--
-- Asya's "GABUNGAN BS" PDF is her weekly *worksheet* — the money she is booking
-- / expects, NOT confirmed cash in the bank. Rows imported from that PDF land
-- as type='cashout_worksheet' (a planning/draft state) and only get promoted to
-- a real 'invoice_payment' once a bank reconciliation confirms the money landed.
-- This keeps the headline P&L (cashbook_summary totals) honest — worksheet rows
-- are excluded from income/net/margin — while still letting Asya see the pending
-- mass in the by_type breakdown.
--
-- Postgres has no ALTER-CHECK-value: the only way to add an allowed value to a
-- CHECK constraint is DROP + re-ADD with the full list. The constraint is named
-- explicitly ('ck_cashout_type') in migration 238, so IF EXISTS is safe whether
-- or not it has been applied. Idempotent.

ALTER TABLE weekly_cashout DROP CONSTRAINT IF EXISTS ck_cashout_type;

ALTER TABLE weekly_cashout ADD CONSTRAINT ck_cashout_type
    CHECK (type IN (
        'invoice_payment', 'expense', 'payroll', 'commission',
        'bank_fee', 'pnbp_payment', 'tax_payment', 'refund', 'manual',
        'cashout_worksheet'
    ));

-- === ROLLBACK ===
ALTER TABLE weekly_cashout DROP CONSTRAINT IF EXISTS ck_cashout_type;

ALTER TABLE weekly_cashout ADD CONSTRAINT ck_cashout_type
    CHECK (type IN (
        'invoice_payment', 'expense', 'payroll', 'commission',
        'bank_fee', 'pnbp_payment', 'tax_payment', 'refund', 'manual'
    ));
