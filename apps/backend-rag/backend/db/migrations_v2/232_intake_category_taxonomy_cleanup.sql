-- 232_intake_category_taxonomy_cleanup.sql
--
-- Intake-review document-category taxonomy cleanup.
--
-- Owner decisions (2026-06-17):
--   1. Dedup: ITAS/ITAP are the canonical post-Cipta-Kerja stay-permit terms.
--      Deactivate (active=false) the redundant KITAS/KITAP rows. NOT a delete --
--      the dropdown endpoints filter `WHERE active=true`, so active=false simply
--      removes them from the UI and is fully reversible (see ROLLBACK below).
--   2. Add two immigration categories: e_visa (E-Visa) and itk (ITK / Izin
--      Tinggal Kunjungan, a visit stay permit distinct from ITAS/ITAP).
--   3. (Self-containment) re-assert the 9 rows that had drifted into the live DB
--      ahead of the apply_migration_033 seed-of-record (itas, itap, stm,
--      izin_usaha, virtual_office, e_spt, skt, bank_statement, health_cert).
--      The PRIMARY drift fix lives in apply_migration_033.py; these INSERT ...
--      ON CONFLICT DO NOTHING are a no-op on Pro (rows already present) and only
--      make this migration converge a fresh DB.
--
-- SCOPE: `document_categories` is a Pro-LOCAL-ONLY table (DSN
--   nuzantara@127.0.0.1:5432/nuzantara_dev). It does NOT exist on Fly. This
--   migration is a harmless no-op where the table is absent -- guarded with
--   to_regclass() so it RAISE NOTICEs and skips instead of erroring.
--
-- IDEMPOTENT: re-running changes nothing. UPDATEs converge to the same state;
--   the new rows use ON CONFLICT (code) DO UPDATE (re-activating + refreshing
--   metadata); the drift rows use ON CONFLICT (code) DO NOTHING.
--
-- sort_order note: the dropdown query is `ORDER BY sort_order, name` with
--   `WHERE active=true`. e_visa shares sort_order=5 with voa (name tiebreak puts
--   "E-Visa" before "Visa on Arrival" -> renders in the visa cluster); itk shares
--   sort_order=7 with itap ("ITAP..." before "ITK..." -> renders right after itap
--   in the izin-tinggal cluster). Shared sort_order is fine -- `code` is the only
--   UNIQUE column, ties break deterministically by name. Zero renumbering of
--   existing canonical rows (surgical).

-- === FORWARD ===
DO $$
BEGIN
  IF to_regclass('public.document_categories') IS NULL THEN
    RAISE NOTICE 'document_categories absent (Fly) -- skipping intake taxonomy cleanup';
    RETURN;
  END IF;

  -- 1. Dedup: deactivate redundant KITAS/KITAP (ITAS/ITAP stay canonical).
  UPDATE document_categories SET active = false WHERE code IN ('kitas', 'kitap');

  -- 2. Add E-Visa + ITK (immigration). DO UPDATE makes re-runs converge and
  --    re-activates the row if someone had deactivated it.
  INSERT INTO document_categories (code, name, category_group, description, has_expiry, sort_order, active) VALUES
    ('e_visa', 'E-Visa', 'immigration', 'Electronic visa (e-VOA / e-visa index)', true, 5, true),
    ('itk', 'ITK (Izin Tinggal Kunjungan)', 'immigration', 'Visit stay permit (distinct from ITAS/ITAP)', true, 7, true)
  ON CONFLICT (code) DO UPDATE SET
    name           = EXCLUDED.name,
    category_group = EXCLUDED.category_group,
    description    = EXCLUDED.description,
    has_expiry     = EXCLUDED.has_expiry,
    sort_order     = EXCLUDED.sort_order,
    active         = true;

  -- 3. Drift convergence: assert the 9 live-only rows so a fresh DB matches Pro.
  --    No-op on Pro (rows exist). Matches apply_migration_033.py seed verbatim.
  INSERT INTO document_categories (code, name, category_group, has_expiry, sort_order) VALUES
    ('itas',           'ITAS (Izin Tinggal Terbatas)',  'immigration', true,  6),
    ('itap',           'ITAP (Izin Tinggal Tetap)',     'immigration', true,  7),
    ('stm',            'STM (Surat Tanda Melapor)',      'immigration', true,  13),
    ('izin_usaha',     'Izin Usaha (Business License)',  'pma',         true,  26),
    ('virtual_office', 'Virtual Office Agreement',       'pma',         true,  27),
    ('e_spt',          'e-SPT Filing',                   'tax',         false, 33),
    ('skt',            'SKT (Tax Registration Letter)',  'tax',         false, 37),
    ('bank_statement', 'Bank Statement',                 'personal',    false, 46),
    ('health_cert',    'Health Certificate',             'personal',    true,  47)
  ON CONFLICT (code) DO NOTHING;

  RAISE NOTICE 'intake taxonomy cleanup applied: KITAS/KITAP deactivated, E-Visa+ITK added, 9 drift rows asserted';
END $$;

-- === ROLLBACK ===
-- DO $$
-- BEGIN
--   IF to_regclass('public.document_categories') IS NULL THEN
--     RAISE NOTICE 'document_categories absent (Fly) -- nothing to roll back';
--     RETURN;
--   END IF;
--   -- Re-activate the deduped rows.
--   UPDATE document_categories SET active = true WHERE code IN ('kitas', 'kitap');
--   -- Remove the categories added by this migration.
--   DELETE FROM document_categories WHERE code IN ('e_visa', 'itk');
--   -- (The 9 drift rows are intentionally NOT removed on rollback -- they predate
--   --  this migration and are owned by apply_migration_033.)
-- END $$;
