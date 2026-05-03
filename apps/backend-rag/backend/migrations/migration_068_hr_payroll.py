"""
Migration 066: HR/Payroll Module Schema

Creates 9 tables for the HR/Payroll module:
- hr_employees, hr_bonus_rates, hr_bonus_ledger
- hr_payroll_periods, hr_payslips, hr_deductions
- hr_leave_types, hr_leave_balances, hr_leave_requests

All money columns stored as BIGINT IDR (no decimals).
FK references: team_members(id) VARCHAR(36), practices(id) INT, practice_types(code) VARCHAR(50).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


UPGRADE_SQL = """
-- ============================================
-- HR/PAYROLL SCHEMA - UPGRADE (Migration 066)
-- ============================================

-- 1. hr_employees — extends team_members with HR/payroll data
CREATE TABLE IF NOT EXISTS hr_employees (
    id              SERIAL PRIMARY KEY,
    team_member_id  VARCHAR(36) NOT NULL UNIQUE REFERENCES team_members(id) ON DELETE RESTRICT,
    hire_date       DATE NOT NULL,
    base_salary_idr BIGINT NOT NULL CHECK (base_salary_idr >= 0),
    bank_name       VARCHAR(100),
    bank_account    VARCHAR(100),
    bank_account_holder VARCHAR(255),
    npwp            VARCHAR(32),
    ptkp_status     VARCHAR(10) NOT NULL DEFAULT 'TK/0',
    bpjs_kesehatan_number   VARCHAR(32),
    bpjs_ketenagakerjaan_number VARCHAR(32),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_hr_employees_ptkp CHECK (
        ptkp_status IN ('TK/0','TK/1','TK/2','TK/3','K/0','K/1','K/2','K/3')
    )
);

-- 2. hr_bonus_rates — configurable bonus per practice type
CREATE TABLE IF NOT EXISTS hr_bonus_rates (
    id              SERIAL PRIMARY KEY,
    practice_type_code VARCHAR(50) NOT NULL UNIQUE,
    amount_idr      BIGINT NOT NULL CHECK (amount_idr >= 0),
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_hr_bonus_rates_window CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

-- 3. hr_payroll_periods — monthly payroll cycles
CREATE TABLE IF NOT EXISTS hr_payroll_periods (
    id              SERIAL PRIMARY KEY,
    payroll_month   SMALLINT NOT NULL CHECK (payroll_month BETWEEN 1 AND 12),
    payroll_year    SMALLINT NOT NULL CHECK (payroll_year BETWEEN 2000 AND 2100),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    locked_at       TIMESTAMPTZ,
    created_by      VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_by     VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_at     TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_hr_payroll_period UNIQUE (payroll_month, payroll_year),
    CONSTRAINT ck_hr_payroll_dates CHECK (period_end >= period_start),
    CONSTRAINT ck_hr_payroll_status CHECK (
        status IN ('draft', 'calculated', 'approved', 'paid')
    )
);

-- 4. hr_payslips — per-employee per-period breakdown
CREATE TABLE IF NOT EXISTS hr_payslips (
    id                  SERIAL PRIMARY KEY,
    payroll_period_id   INTEGER NOT NULL REFERENCES hr_payroll_periods(id) ON DELETE RESTRICT,
    employee_id         INTEGER NOT NULL REFERENCES hr_employees(id) ON DELETE RESTRICT,
    base_salary_idr     BIGINT NOT NULL CHECK (base_salary_idr >= 0),
    bonus_total_idr     BIGINT NOT NULL DEFAULT 0 CHECK (bonus_total_idr >= 0),
    allowance_total_idr BIGINT NOT NULL DEFAULT 0 CHECK (allowance_total_idr >= 0),
    deduction_total_idr BIGINT NOT NULL DEFAULT 0 CHECK (deduction_total_idr >= 0),
    thr_idr             BIGINT NOT NULL DEFAULT 0 CHECK (thr_idr >= 0),
    net_salary_idr      BIGINT NOT NULL,
    notes               TEXT,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by         VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_hr_payslip_emp_period UNIQUE (employee_id, payroll_period_id)
);

-- 5. hr_bonus_ledger — individual bonus entries linked to practices
CREATE TABLE IF NOT EXISTS hr_bonus_ledger (
    id              BIGSERIAL PRIMARY KEY,
    practice_id     INTEGER NOT NULL REFERENCES practices(id) ON DELETE RESTRICT,
    employee_id     INTEGER NOT NULL REFERENCES hr_employees(id) ON DELETE RESTRICT,
    payroll_period_id INTEGER REFERENCES hr_payroll_periods(id) ON DELETE SET NULL,
    bonus_rate_id   INTEGER REFERENCES hr_bonus_rates(id) ON DELETE SET NULL,
    practice_type_code VARCHAR(50) NOT NULL,
    amount_idr      BIGINT NOT NULL CHECK (amount_idr >= 0),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    awarded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    awarded_by      VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_by     VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_at     TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_hr_bonus_practice_emp UNIQUE (practice_id, employee_id),
    CONSTRAINT ck_hr_bonus_status CHECK (
        status IN ('pending', 'approved', 'rejected', 'paid', 'reversed')
    )
);

-- 6. hr_deductions — per-payslip deduction items
CREATE TABLE IF NOT EXISTS hr_deductions (
    id              SERIAL PRIMARY KEY,
    payslip_id      INTEGER NOT NULL REFERENCES hr_payslips(id) ON DELETE CASCADE,
    deduction_type  VARCHAR(40) NOT NULL,
    label           VARCHAR(100) NOT NULL,
    amount_idr      BIGINT NOT NULL CHECK (amount_idr >= 0),
    is_employer     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_hr_deduction_type CHECK (
        deduction_type IN (
            'bpjs_kes_employee', 'bpjs_kes_employer',
            'bpjs_jht_employee', 'bpjs_jht_employer',
            'bpjs_jkk', 'bpjs_jkm',
            'bpjs_jp_employee', 'bpjs_jp_employer',
            'pph21',
            'loan', 'other'
        )
    )
);

-- 7. hr_leave_types — leave category definitions
CREATE TABLE IF NOT EXISTS hr_leave_types (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    default_days    INTEGER NOT NULL CHECK (default_days >= 0),
    is_paid         BOOLEAN NOT NULL DEFAULT TRUE,
    requires_document BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. hr_leave_balances — per-employee per-year balances
CREATE TABLE IF NOT EXISTS hr_leave_balances (
    id              SERIAL PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES hr_employees(id) ON DELETE CASCADE,
    leave_type_id   INTEGER NOT NULL REFERENCES hr_leave_types(id) ON DELETE RESTRICT,
    balance_year    SMALLINT NOT NULL CHECK (balance_year BETWEEN 2000 AND 2100),
    allocated_days  INTEGER NOT NULL DEFAULT 0 CHECK (allocated_days >= 0),
    carried_over    INTEGER NOT NULL DEFAULT 0 CHECK (carried_over >= 0),
    used_days       INTEGER NOT NULL DEFAULT 0 CHECK (used_days >= 0),
    pending_days    INTEGER NOT NULL DEFAULT 0 CHECK (pending_days >= 0),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_hr_leave_bal UNIQUE (employee_id, leave_type_id, balance_year),
    CONSTRAINT ck_hr_leave_bal_nonneg CHECK (
        (allocated_days + carried_over) >= (used_days + pending_days)
    )
);

-- 9. hr_leave_requests — leave request with approval workflow
CREATE TABLE IF NOT EXISTS hr_leave_requests (
    id              BIGSERIAL PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES hr_employees(id) ON DELETE CASCADE,
    leave_type_id   INTEGER NOT NULL REFERENCES hr_leave_types(id) ON DELETE RESTRICT,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    total_days      INTEGER NOT NULL CHECK (total_days > 0),
    reason          TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by     VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_hr_leave_req_dates CHECK (end_date >= start_date),
    CONSTRAINT ck_hr_leave_req_status CHECK (
        status IN ('pending', 'approved', 'rejected', 'cancelled')
    )
);

-- ========================================
-- INDEXES
-- ========================================
CREATE INDEX IF NOT EXISTS idx_hr_employees_active ON hr_employees(is_active);
CREATE INDEX IF NOT EXISTS idx_hr_employees_tm ON hr_employees(team_member_id);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_rates_active ON hr_bonus_rates(is_active, practice_type_code);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_ledger_emp ON hr_bonus_ledger(employee_id, awarded_at DESC);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_ledger_practice ON hr_bonus_ledger(practice_id);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_ledger_period ON hr_bonus_ledger(payroll_period_id);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_ledger_status ON hr_bonus_ledger(status);
CREATE INDEX IF NOT EXISTS idx_hr_payroll_status ON hr_payroll_periods(status);
CREATE INDEX IF NOT EXISTS idx_hr_payslips_period ON hr_payslips(payroll_period_id);
CREATE INDEX IF NOT EXISTS idx_hr_payslips_emp ON hr_payslips(employee_id);
CREATE INDEX IF NOT EXISTS idx_hr_leave_req_emp ON hr_leave_requests(employee_id, status, start_date DESC);
CREATE INDEX IF NOT EXISTS idx_hr_leave_bal_emp ON hr_leave_balances(employee_id, balance_year);
CREATE INDEX IF NOT EXISTS idx_hr_deductions_payslip ON hr_deductions(payslip_id);

-- ========================================
-- TRIGGERS: updated_at
-- ========================================
CREATE OR REPLACE FUNCTION hr_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'hr_employees', 'hr_bonus_rates', 'hr_payroll_periods',
        'hr_payslips', 'hr_bonus_ledger', 'hr_deductions',
        'hr_leave_types', 'hr_leave_balances', 'hr_leave_requests'
    ]) LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I; '
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION hr_set_updated_at();',
            tbl, tbl, tbl, tbl
        );
    END LOOP;
END;
$$;

-- ========================================
-- TRIGGER: bonus only for completed practices
-- ========================================
CREATE OR REPLACE FUNCTION hr_validate_completed_practice()
RETURNS TRIGGER AS $$
DECLARE
    v_status TEXT;
BEGIN
    SELECT status INTO v_status FROM practices WHERE id = NEW.practice_id;
    IF v_status IS NULL OR v_status <> 'completed' THEN
        RAISE EXCEPTION 'Practice % must be completed before bonus entry (status=%)',
            NEW.practice_id, COALESCE(v_status, 'NOT_FOUND');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hr_bonus_validate ON hr_bonus_ledger;
CREATE TRIGGER trg_hr_bonus_validate
BEFORE INSERT OR UPDATE OF practice_id ON hr_bonus_ledger
FOR EACH ROW EXECUTE FUNCTION hr_validate_completed_practice();

-- ========================================
-- TRIGGER: payroll period locking
-- ========================================
CREATE OR REPLACE FUNCTION hr_enforce_period_lock()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('approved', 'paid') THEN
            RAISE EXCEPTION 'Cannot delete locked payroll period %', OLD.id;
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'paid' THEN
        RAISE EXCEPTION 'Payroll period % is paid and immutable', OLD.id;
    END IF;

    IF OLD.status = 'approved' AND NEW.status <> 'paid' THEN
        RAISE EXCEPTION 'Approved period % only allows transition to paid', OLD.id;
    END IF;

    IF NEW.status = 'approved' AND OLD.status <> 'approved' THEN
        NEW.approved_at = COALESCE(NEW.approved_at, NOW());
        NEW.locked_at = COALESCE(NEW.locked_at, NOW());
    END IF;

    IF NEW.status = 'paid' AND OLD.status <> 'paid' THEN
        NEW.paid_at = COALESCE(NEW.paid_at, NOW());
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hr_period_lock ON hr_payroll_periods;
CREATE TRIGGER trg_hr_period_lock
BEFORE UPDATE OR DELETE ON hr_payroll_periods
FOR EACH ROW EXECUTE FUNCTION hr_enforce_period_lock();

-- ========================================
-- TRIGGER: prevent mutations on locked payslips
-- ========================================
CREATE OR REPLACE FUNCTION hr_prevent_locked_payslip_mutation()
RETURNS TRIGGER AS $$
DECLARE
    v_period_id INTEGER;
    v_status TEXT;
BEGIN
    v_period_id := COALESCE(NEW.payroll_period_id, OLD.payroll_period_id);
    SELECT status INTO v_status FROM hr_payroll_periods WHERE id = v_period_id;
    IF v_status IN ('approved', 'paid') THEN
        RAISE EXCEPTION 'Cannot modify payslip: period % is %', v_period_id, v_status;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hr_payslip_lock ON hr_payslips;
CREATE TRIGGER trg_hr_payslip_lock
BEFORE INSERT OR UPDATE OR DELETE ON hr_payslips
FOR EACH ROW EXECUTE FUNCTION hr_prevent_locked_payslip_mutation();

-- ========================================
-- SEED: leave types (Indonesian labor law)
-- ========================================
INSERT INTO hr_leave_types (code, name, description, default_days, is_paid, requires_document)
VALUES
    ('annual',    'Annual Leave',    'Cuti tahunan - 12 hari setelah 12 bulan kerja (UU 13/2003 Pasal 79)', 12, TRUE, FALSE),
    ('sick',      'Sick Leave',      'Cuti sakit - dengan surat dokter setelah 3 hari', 0, TRUE, TRUE),
    ('maternity', 'Maternity Leave', 'Cuti melahirkan - 3 bulan (1.5 sebelum + 1.5 sesudah, UU 13/2003 Pasal 82)', 90, TRUE, TRUE),
    ('paternity', 'Paternity Leave', 'Cuti ayah - 2 hari (UU 13/2003 Pasal 93)', 2, TRUE, FALSE),
    ('marriage',  'Marriage Leave',  'Cuti nikah - 3 hari (UU 13/2003 Pasal 93)', 3, TRUE, FALSE),
    ('bereavement','Bereavement',    'Cuti duka - 2 hari (keluarga inti, UU 13/2003 Pasal 93)', 2, TRUE, FALSE),
    ('unpaid',    'Unpaid Leave',    'Cuti tanpa gaji', 0, FALSE, FALSE)
ON CONFLICT (code) DO NOTHING;

-- ========================================
-- SEED: bonus rates (initial values)
-- ========================================
INSERT INTO hr_bonus_rates (practice_type_code, amount_idr, effective_from, is_active, notes)
VALUES
    ('tourist_visa',    250000,  '2026-01-01', TRUE, 'B211A / tourist visa'),
    ('visa_extension',  200000,  '2026-01-01', TRUE, 'Visa extension'),
    ('kitas',           750000,  '2026-01-01', TRUE, 'New KITAS'),
    ('kitas_extension', 600000,  '2026-01-01', TRUE, 'KITAS extension'),
    ('investor_kitas',  900000,  '2026-01-01', TRUE, 'Investor KITAS'),
    ('npwp',            150000,  '2026-01-01', TRUE, 'NPWP registration'),
    ('pph21_monthly',   200000,  '2026-01-01', TRUE, 'Monthly PPh21 filing'),
    ('nib_oss',         350000,  '2026-01-01', TRUE, 'NIB/OSS registration'),
    ('pt_pma',          1500000, '2026-01-01', TRUE, 'PT PMA setup'),
    ('lkpm',            300000,  '2026-01-01', TRUE, 'LKPM quarterly report')
ON CONFLICT (practice_type_code) DO UPDATE SET
    amount_idr = EXCLUDED.amount_idr,
    effective_from = EXCLUDED.effective_from,
    is_active = EXCLUDED.is_active,
    notes = EXCLUDED.notes,
    updated_at = NOW();
"""


DOWNGRADE_SQL = """
-- ============================================
-- HR/PAYROLL SCHEMA - DOWNGRADE
-- ============================================

-- Drop lock triggers
DROP TRIGGER IF EXISTS trg_hr_payslip_lock ON hr_payslips;
DROP TRIGGER IF EXISTS trg_hr_period_lock ON hr_payroll_periods;
DROP TRIGGER IF EXISTS trg_hr_bonus_validate ON hr_bonus_ledger;

-- Drop updated_at triggers
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'hr_employees', 'hr_bonus_rates', 'hr_payroll_periods',
        'hr_payslips', 'hr_bonus_ledger', 'hr_deductions',
        'hr_leave_types', 'hr_leave_balances', 'hr_leave_requests'
    ]) LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I', tbl, tbl);
    END LOOP;
END;
$$;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS hr_deductions;
DROP TABLE IF EXISTS hr_leave_requests;
DROP TABLE IF EXISTS hr_leave_balances;
DROP TABLE IF EXISTS hr_leave_types;
DROP TABLE IF EXISTS hr_bonus_ledger;
DROP TABLE IF EXISTS hr_payslips;
DROP TABLE IF EXISTS hr_payroll_periods;
DROP TABLE IF EXISTS hr_bonus_rates;
DROP TABLE IF EXISTS hr_employees;

-- Drop functions
DROP FUNCTION IF EXISTS hr_prevent_locked_payslip_mutation();
DROP FUNCTION IF EXISTS hr_enforce_period_lock();
DROP FUNCTION IF EXISTS hr_validate_completed_practice();
DROP FUNCTION IF EXISTS hr_set_updated_at();
"""


async def upgrade(conn: Any) -> None:
    """Apply HR/Payroll schema."""
    await conn.execute(UPGRADE_SQL)
    logger.info("Migration 066: HR/Payroll schema created (9 tables, triggers, seed data)")


async def downgrade(conn: Any) -> None:
    """Rollback HR/Payroll schema."""
    await conn.execute(DOWNGRADE_SQL)
    logger.info("Migration 066: HR/Payroll schema dropped")
