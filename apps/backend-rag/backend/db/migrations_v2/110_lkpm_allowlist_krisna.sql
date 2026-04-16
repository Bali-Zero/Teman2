-- ============================================================
-- 110_lkpm_allowlist_krisna.sql
-- Add Krisna (Executive Consultant) to the lkpm_reports assignee allowlist
-- Date: 2026-04-16
--
-- The PDF "Client LKPM Report Q1 2026.pdf" lists Krisna as the handler
-- for 4 PTs (Bali Accommodation Management, Jungle Dream House,
-- Bali Nea Karma, Urban Jungle Bali, Karta Entertainment Found).
-- He doesn't have a .tax@ sub-alias so we whitelist krisna@balizero.com.
--
-- Must be kept in sync with:
--   - backend/app/routers/lkpm.py:LKPM_ASSIGNEES
--   - backend/app/routers/crm_clients.py:TAX_CONSULTANT_VALUES (if referenced)
-- ============================================================

ALTER TABLE lkpm_reports
  DROP CONSTRAINT IF EXISTS lkpm_reports_assigned_to_check;

ALTER TABLE lkpm_reports
  ADD CONSTRAINT lkpm_reports_assigned_to_check
  CHECK (
    lkpm_assigned_to IS NULL
    OR lkpm_assigned_to IN (
      'veronika.tax@balizero.com',
      'kadek.tax@balizero.com',
      'dewaayu.tax@balizero.com',
      'angel.tax@balizero.com',
      'faisha.tax@balizero.com',
      'krisna@balizero.com'
    )
  );
