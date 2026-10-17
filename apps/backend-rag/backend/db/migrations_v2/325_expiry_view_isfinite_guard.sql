-- 325_expiry_view_isfinite_guard.sql
--
-- THE DEFECT (measured on PROD 2026-10-12, read-only): every read of
-- `client_expiry_alerts_view` fails with `cannot subtract infinite dates`.
-- One active client row (client_id 12336) holds an infinite
-- `clients.passport_expiry`; the view computes `<expiry> - CURRENT_DATE` in
-- each of its four UNION ALL branches and PostgreSQL raises on the first
-- infinite operand, so ONE bad row takes down the whole view for every
-- caller: crm_enhanced.py, crm_enhanced_alerts.py, team_crm_tools.py and
-- scripts/s7_yield_draft_local.py (the weekly S7 yield job ends rc=3).
--
-- THE VIEW TEXT BELOW IS THE LIVE `pg_get_viewdef` OUTPUT, not the archaic
-- apply_migration_033.py: same ten columns, same order, same types (the
-- CREATE OR REPLACE VIEW contract), and `client_profile_view` depends on it.
-- Two guards per branch, both needed:
--   1. `AND isfinite(<col>)` in the WHERE drops the row from the view.
--   2. `days_until_expiry` is a CASE that only subtracts a finite date.
--      A consumer predicate on `days_until_expiry` (crm_enhanced_alerts.py
--      filters on it) is pushed down into each UNION branch, and PostgreSQL
--      orders scan quals by cost, not by the order they are written in: the
--      WHERE guard alone does not promise the subtraction never runs on the
--      bad row. CASE evaluation order does.
--
-- WRITE SIDE: a CHECK (<col> IS NULL OR isfinite(<col>)) on each of the four
-- expiry columns, added NOT VALID: it binds every new INSERT/UPDATE without
-- scanning, so the existing bad row does not abort this migration. Cleaning
-- that row and `VALIDATE CONSTRAINT` are an operator step, not this file.
--
-- GUARDED ON EXISTENCE: the view and `client_family_members` have no
-- migration of their own (prod was bootstrapped by hand); CI's fresh DB
-- (SQLModel bootstrap + apply-all) has `clients` and `documents` but not
-- `client_family_members`. The view is (re)created only when all three
-- source tables exist; each CHECK only where its column exists. Re-running
-- the file is a no-op (pg_constraint is checked per table OID).

DO $m325$
DECLARE
    target record;
    rel regclass;
BEGIN
    IF to_regclass('clients') IS NOT NULL
       AND to_regclass('client_family_members') IS NOT NULL
       AND to_regclass('documents') IS NOT NULL THEN
        EXECUTE $view$
CREATE OR REPLACE VIEW client_expiry_alerts_view AS
 SELECT 'client'::text AS entity_type,
    c.id AS entity_id,
    c.full_name AS entity_name,
    c.id AS client_id,
    c.full_name AS client_name,
    'passport'::text AS document_type,
    c.passport_expiry AS expiry_date,
        CASE
            WHEN isfinite(c.passport_expiry) THEN c.passport_expiry - CURRENT_DATE
            ELSE NULL::integer
        END AS days_until_expiry,
        CASE
            WHEN c.passport_expiry <= CURRENT_DATE THEN 'expired'::text
            WHEN c.passport_expiry <= (CURRENT_DATE + '8 mons'::interval) THEN 'red'::text
            WHEN c.passport_expiry <= (CURRENT_DATE + '1 year'::interval) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM clients c
  WHERE c.passport_expiry IS NOT NULL AND isfinite(c.passport_expiry) AND c.status::text = 'active'::text
UNION ALL
 SELECT 'family_member'::text AS entity_type,
    fm.id AS entity_id,
    fm.full_name AS entity_name,
    fm.client_id,
    c.full_name AS client_name,
    'passport'::text AS document_type,
    fm.passport_expiry AS expiry_date,
        CASE
            WHEN isfinite(fm.passport_expiry) THEN fm.passport_expiry - CURRENT_DATE
            ELSE NULL::integer
        END AS days_until_expiry,
        CASE
            WHEN fm.passport_expiry <= CURRENT_DATE THEN 'expired'::text
            WHEN fm.passport_expiry <= (CURRENT_DATE + '8 mons'::interval) THEN 'red'::text
            WHEN fm.passport_expiry <= (CURRENT_DATE + '1 year'::interval) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM client_family_members fm
     JOIN clients c ON fm.client_id = c.id
  WHERE fm.passport_expiry IS NOT NULL AND isfinite(fm.passport_expiry)
UNION ALL
 SELECT 'family_member'::text AS entity_type,
    fm.id AS entity_id,
    fm.full_name AS entity_name,
    fm.client_id,
    c.full_name AS client_name,
    'visa'::text AS document_type,
    fm.visa_expiry AS expiry_date,
        CASE
            WHEN isfinite(fm.visa_expiry) THEN fm.visa_expiry - CURRENT_DATE
            ELSE NULL::integer
        END AS days_until_expiry,
        CASE
            WHEN fm.visa_expiry <= CURRENT_DATE THEN 'expired'::text
            WHEN fm.visa_expiry <= (CURRENT_DATE + '8 mons'::interval) THEN 'red'::text
            WHEN fm.visa_expiry <= (CURRENT_DATE + '1 year'::interval) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM client_family_members fm
     JOIN clients c ON fm.client_id = c.id
  WHERE fm.visa_expiry IS NOT NULL AND isfinite(fm.visa_expiry)
UNION ALL
 SELECT 'document'::text AS entity_type,
    d.id AS entity_id,
    d.document_type AS entity_name,
    d.client_id,
    c.full_name AS client_name,
    d.document_type,
    d.expiry_date,
        CASE
            WHEN isfinite(d.expiry_date) THEN d.expiry_date - CURRENT_DATE
            ELSE NULL::integer
        END AS days_until_expiry,
        CASE
            WHEN d.expiry_date <= CURRENT_DATE THEN 'expired'::text
            WHEN d.expiry_date <= (CURRENT_DATE + '8 mons'::interval) THEN 'red'::text
            WHEN d.expiry_date <= (CURRENT_DATE + '1 year'::interval) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM documents d
     JOIN clients c ON d.client_id = c.id
  WHERE d.expiry_date IS NOT NULL AND isfinite(d.expiry_date) AND d.status::text <> 'rejected'::text AND (d.is_archived IS NULL OR d.is_archived = false)
$view$;
    END IF;

    FOR target IN
        SELECT * FROM (VALUES
            ('clients', 'passport_expiry', 'clients_passport_expiry_finite'),
            ('client_family_members', 'passport_expiry', 'client_family_members_passport_expiry_finite'),
            ('client_family_members', 'visa_expiry', 'client_family_members_visa_expiry_finite'),
            ('documents', 'expiry_date', 'documents_expiry_date_finite')
        ) AS t(tbl, col, con)
    LOOP
        rel := to_regclass(target.tbl);
        CONTINUE WHEN rel IS NULL;
        CONTINUE WHEN NOT EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = rel AND attname = target.col AND NOT attisdropped
        );
        CONTINUE WHEN EXISTS (
            SELECT 1 FROM pg_constraint WHERE conrelid = rel AND conname = target.con
        );
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I CHECK (%I IS NULL OR isfinite(%I)) NOT VALID',
            rel, target.con, target.col, target.col
        );
    END LOOP;
END
$m325$;

-- === ROLLBACK ===
-- Drops the four write-side CHECKs only. The view keeps its guards: the
-- pre-325 text is the one that fails on any infinite date, so restoring it
-- would re-break every consumer rather than undo a risk.
ALTER TABLE IF EXISTS clients DROP CONSTRAINT IF EXISTS clients_passport_expiry_finite;
ALTER TABLE IF EXISTS client_family_members DROP CONSTRAINT IF EXISTS client_family_members_passport_expiry_finite;
ALTER TABLE IF EXISTS client_family_members DROP CONSTRAINT IF EXISTS client_family_members_visa_expiry_finite;
ALTER TABLE IF EXISTS documents DROP CONSTRAINT IF EXISTS documents_expiry_date_finite;
