-- ============================================================
-- 182_companies_tax_dept_folder.sql
-- CRM-Guardian Phase 1.6 — tax-dept folder linkage
--
-- The Bali Zero tax department maintains a SHARED Drive structure
-- (`Members/<TeamMember>/<COMPANY_NAME>/`) holding SPT/PPN/PPh/LKPM
-- documents that are NOT in the cliente canonical folder NOR in the
-- linked company's `companies.google_drive_folder_id`.
--
-- Discovery script `crm_guardian_tax_dept_discovery.py` ran 2026-05-18
-- and matched 20 tax-dept company folders to existing `companies` rows
-- via 3-tier fuzzy match (T3 Levenshtein <= 3 on normalized names).
-- This migration adds the column the worker reads as its 3rd source
-- alongside cliente root + companies.google_drive_folder_id.
--
-- After the writer script applies (separate PR), the worker will
-- include tax-dept folder content automatically: same aggregation,
-- same OCR cache, same prompt — just one more `source_folder_id` in
-- the inventory.
--
-- Depends on:
--   181_crm_guardian_file_content_cache.sql (Phase 1.5 OCR cache base)
-- Decision memo:
--   research/crm-guardian/2026-05-18-phase-1.5-ocr-layer-plan.md
--   (Phase 1.6 section to be added; see MOS decision 2026-05-18)
-- ============================================================

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS tax_dept_folder_id TEXT;

COMMENT ON COLUMN companies.tax_dept_folder_id IS
  'Phase 1.6 (2026-05-18): Drive folder ID inside Members/<TeamMember>/<COMPANY>/ '
  'in the tax department shared Drive. NULL when the company has no tax-dept '
  'entry (most companies). Populated by scripts/crm_guardian_tax_dept_apply.py '
  'from a discovery report. Worker reads it as 3rd cross-folder source.';

CREATE INDEX IF NOT EXISTS ix_companies_tax_dept_folder
    ON companies (tax_dept_folder_id)
    WHERE tax_dept_folder_id IS NOT NULL;

-- Audit
INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'enable_phase1.6_tax_dept_folder_column',
    'system',
    'companies.tax_dept_folder_id',
    NULL,
    jsonb_build_object('column_exists', false),
    jsonb_build_object(
        'column_exists', true,
        'migration', '182_companies_tax_dept_folder',
        'note', 'Phase 1.6 schema extension. Writer apply step + worker patch follow.'
    ),
    'success',
    false
);

-- === ROLLBACK ===
-- Drop the column. tax-dept folder data, if populated, is lost — recoverable
-- by re-running the discovery script and writer.

DROP INDEX IF EXISTS ix_companies_tax_dept_folder;
ALTER TABLE companies DROP COLUMN IF EXISTS tax_dept_folder_id;

INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'disable_phase1.6_tax_dept_folder_column',
    'system',
    'companies.tax_dept_folder_id',
    NULL,
    jsonb_build_object('column_exists', true),
    jsonb_build_object('column_exists', false, 'migration', '182_companies_tax_dept_folder', 'rolled_back', true),
    'success',
    false
);
