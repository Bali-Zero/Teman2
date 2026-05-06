-- Migration 157: 2026 pricing delta for practice_types catalog
--
-- Owner-approved 2026-05-06: do NOT replace any existing 2025 entries
-- (some carry FK references on live practices). Only:
--   1. Update prices on entries whose 2026 price differs from 2025
--   2. INSERT brand-new 2026 services that did not exist in 2025
--
-- Sources:
--   - Existing 2025 catalog: migration_066_populate_practice_types_from_pricing.py
--     (62 services + 2 tax inline + Bridging Visa from migration_148)
--   - 2026 source of truth: backend/data/bali_zero_official_prices_2026.json
--     (98 services across 9 categories)
--
-- Categories added (decision Q1=B + Q2=a, 2026-05-06 owner approval):
--   tax_monthly         (4 monthly basic tiers, no LKPM/Annual)
--   tax_monthly_bundled (4 monthly bundled tiers, incl. LKPM/Annual)
--   tax_annual          (4 yearly packages A/B/C/D + Annual Company ZERO)
--   tax_standalone      (4 LKPM/Annual stand-alone fees)
--   ...plus 7 consultant_services entries land in `tax` (per Q2=a:
--       Tax dpt sells them — sales sees them under Tax Services).
--
-- Tier-range services (decision Q3=ii, owner approval):
--   For services priced as a range (e.g. 1.8M–2.0M IDR) we insert ONE
--   row per service with base_price = NULL. The Quoted Price field on
--   the New Process form starts blank and the sales person types the
--   negotiated number manually. The notes column keeps the published
--   range for reference.
--
-- Idempotent: ON CONFLICT(code) DO UPDATE so reruns are safe and pick
-- up future tweaks. Same pattern as migration_148_practice_types_bridging_visa.

-- =====================================================================
-- 1. PRICE UPDATES on existing 2025 codes (price changed in 2026)
-- =====================================================================

UPDATE practice_types SET base_price = 12900000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'visa_d1_tourism_5yr';                -- 14M → 12.9M

UPDATE practice_types SET base_price = 1000000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'other_cancel_rptka';                 -- 500k → 1M

UPDATE practice_types SET base_price = 1000000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'other_cancel_wajib_lapor';           -- 500k → 1M

UPDATE practice_types SET base_price = 2200000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'other_passport_10yr';                -- 2M → 2.2M

UPDATE practice_types SET base_price = 2200000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'other_epassport_5yr';                -- 2M → 2.2M

UPDATE practice_types SET base_price = 2700000, updated_at = CURRENT_TIMESTAMP
WHERE code = 'other_epassport_10yr';               -- 2.5M → 2.7M

-- (Domicilie Letter price update intentionally removed — the row is
-- hard-deleted in section 11 below, so updating its price is moot.)

-- C1 Tourism Extension 2026 = +60 days (was +30 in 2025), same price 1.7M
UPDATE practice_types SET
    name = 'C1 Tourism — Extension (+60 days)',
    typical_duration_days = 60,
    description = 'Onshore extension of the C1 Tourism visa for an additional 60 days.',
    updated_at = CURRENT_TIMESTAMP
WHERE code = 'ext_c1_tourism';

-- =====================================================================
-- 2. NEW 2026 services — single_entry_visa
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('visa_c8_journalism',     'C8A,B Journalism Visa',     'Single-entry visa for journalism and media activities (categories C8A, C8B).',                                                   'single_entry_visa', 4000000, NULL, true),
    ('visa_c10_speaker',       'C10 Speaker Visa',          'Single-entry speaker visa for foreign nationals delivering talks, lectures or training sessions at events in Indonesia.',        'single_entry_visa', 3500000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 3. NEW 2026 services — multiple_entry_visa (D2 Business)
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('visa_d2_business_1yr', 'D2 Business (1 Year)',  'Multiple-entry business visa valid 1 year for business meetings and non-employment activities.',  'multiple_entry_visa', 6500000, 365, true),
    ('visa_d2_business_2yr', 'D2 Business (2 Years)', 'Multiple-entry business visa valid 2 years for business meetings and non-employment activities.', 'multiple_entry_visa', 9000000, 730, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 4. NEW 2026 service — KITAS (Born KITAS for foreign children)
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('kitas_born', 'Born KITAS', 'KITAS issuance for foreign children born in Indonesia, processed alongside the birth registration.', 'kitas', 9000000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 5. NEW 2026 services — Tax Monthly (basic, no LKPM/Annual)
--    base_price = NULL because each tier is a 1.8M–2M / 2.5M–3M / etc. range;
--    sales quotes the exact number manually (Q3=ii owner decision).
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('tax_monthly_basic_0_50',     'Monthly Tax Report — 0 to 50 transactions (without LKPM & Annual)',     'Range Rp 1.800.000 – 2.000.000 / month. Bank + Cash transactions combined. LKPM and Annual Tax NOT included.',                            'tax_monthly', NULL, NULL, true),
    ('tax_monthly_basic_50_100',   'Monthly Tax Report — 50 to 100 transactions (without LKPM & Annual)',   'Range Rp 2.500.000 – 3.000.000 / month. Bank + Cash transactions combined. LKPM and Annual Tax NOT included.',                            'tax_monthly', NULL, NULL, true),
    ('tax_monthly_basic_100_200',  'Monthly Tax Report — 100 to 200 transactions (without LKPM & Annual)',  'Range Rp 3.500.000 – 4.500.000 / month. Bank + Cash transactions combined. LKPM and Annual Tax NOT included.',                            'tax_monthly', NULL, NULL, true),
    ('tax_monthly_basic_200_plus', 'Monthly Tax Report — more than 200 transactions (without LKPM & Annual)', 'Rp 5.000.000 / month. Bank + Cash transactions combined. LKPM and Annual Tax NOT included.',                                              'tax_monthly', 5000000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 6. NEW 2026 services — Tax Monthly (bundled with LKPM + Annual)
--    Single price per tier (no range), so base_price is set.
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('tax_monthly_bundled_0_50',     'Monthly Tax Report — 0 to 50 transactions (incl. LKPM & Annual)',     'Bundled monthly bookkeeping, LKPM filing and Annual Tax report for companies with low transaction volume.',     'tax_monthly_bundled', 2500000, NULL, true),
    ('tax_monthly_bundled_50_100',   'Monthly Tax Report — 50 to 100 transactions (incl. LKPM & Annual)',   'Bundled monthly bookkeeping, LKPM filing and Annual Tax report for companies with moderate transaction volume.', 'tax_monthly_bundled', 3500000, NULL, true),
    ('tax_monthly_bundled_100_200',  'Monthly Tax Report — 100 to 200 transactions (incl. LKPM & Annual)',  'Bundled monthly bookkeeping, LKPM filing and Annual Tax report for companies with higher transaction volume.',   'tax_monthly_bundled', 4500000, NULL, true),
    ('tax_monthly_bundled_200_plus', 'Monthly Tax Report — more than 200 transactions (incl. LKPM & Annual)', 'Bundled monthly bookkeeping, LKPM filing and Annual Tax report for companies with high transaction volume.',     'tax_monthly_bundled', 6500000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 7. NEW 2026 services — Tax Annual basic packages A/B/C/D + ZERO
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('tax_annual_pkg_a',         'Annual Basic Package A',  'Up to 100 transactions/year. Income Tax calculation only + yearly Financial Report. No discount applies.',                              'tax_annual', 6000000,  NULL, true),
    ('tax_annual_pkg_b',         'Annual Basic Package B',  '100-200 transactions/year. Income Tax only + yearly Financial Report. No discount applies.',                                          'tax_annual', 9000000,  NULL, true),
    ('tax_annual_pkg_c',         'Annual Basic Package C',  'Up to 100 transactions/year. Income Tax + PPH 21 OR PPH Sewa (choose one) + yearly Financial Report. No discount applies.',           'tax_annual', 12000000, NULL, true),
    ('tax_annual_pkg_d',         'Annual Basic Package D',  '100-200 transactions/year. Income Tax + PPH 21 OR PPH Sewa (choose one) + yearly Financial Report. No discount applies.',             'tax_annual', 15000000, NULL, true),
    ('tax_annual_company_zero',  'Annual Company ZERO',     'Yearly Financial Report only — for dormant companies with no transactions in or out.',                                                'tax_annual', 3000000,  NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 8. NEW 2026 services — Tax stand-alone & compliance fees
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('tax_lkpm_yearly',          'LKPM Yearly Report',                'Stand-alone yearly LKPM (investment realisation) report submitted to BKPM, required for all PT PMA companies.', 'tax_standalone', 4000000, NULL, true),
    ('tax_annual_company',       'Annual Tax Company (SPT Badan)',    'Stand-alone Annual Corporate Tax report (SPT Tahunan PPh Badan) for Indonesian companies.',                   'tax_standalone', 4000000, NULL, true),
    ('tax_annual_personal',      'Annual Tax Personal (SPT OP)',      'Stand-alone Annual Personal Tax report (SPT Tahunan PPh Orang Pribadi) for individual taxpayers. Per person.', 'tax_standalone', 1000000, NULL, true),
    ('tax_annual_personal_addl', 'Annual Tax Personal (additional)',  'Stand-alone Annual Personal Tax report for additional persons beyond the first taxpayer. Per person.',        'tax_standalone', 1500000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 9. NEW 2026 services — Bali Zero Consultant Services
--    Per owner Q2=a: all land in `tax` category (Tax dpt sells them).
--    Coexist with the 2 inline tax entries from migration_066:
--    `tax_registration` (Tax Registration NPWP — 3M) and
--    `tax_annual_reporting` (Annual Tax Reporting — 3M) which we leave
--    untouched per owner rule "non sostituire i service già presenti".
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('tax_npwpd_registration',     'NPWPD Registration',                  'Local tax registration (Nomor Pokok Wajib Pajak Daerah) at the regency or city tax office. Per location.',                       'tax',     2500000, NULL, true),
    ('tax_bpjs_employee',          'BPJS Employee (Tenaga Kerja)',        'Registration with BPJS Ketenagakerjaan, the mandatory Indonesian social security scheme for employees.',                      'tax',     2500000, NULL, true),
    ('tax_bpjs_insurance',         'BPJS Insurance (Kesehatan)',          'Registration with BPJS Kesehatan, the mandatory Indonesian national health insurance scheme.',                                'tax',     2500000, NULL, true),
    ('tax_npwp_personal_coretax',  'NPWP Personal + Coretax Activation',  'Personal Indonesian tax ID (NPWP) issuance with activation on the Coretax platform. Per person.',                              'tax',     1000000, NULL, true),
    ('tax_update_data_coretax',    'Update Data / Coretax Activation',    'Update of taxpayer data (email, phone number, etc.) or stand-alone Coretax activation for an existing NPWP.',                  'tax',     1000000, NULL, true),
    ('tax_efin_application',       'EFIN Application',                    'Application for Electronic Filing Identification Number (EFIN) required to file taxes electronically with the Indonesian tax authority.', 'tax', 1000000, NULL, true),
    ('tax_close_pma_company',      'Close PMA Company',                   'Range Rp 6.000.000 – 7.500.000. Full closure and deregistration of an Indonesian PT PMA, including notarial deed, BKPM and tax authority deregistration. Process up to 1 year.', 'tax', NULL, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 10. NEW 2026 services — Other Process additions
--     Born Report (4M) is intentionally NOT touched: per owner the new
--     Lapor Lahir (Under) / Lapor Lahir (Up) are the 2026 replacement
--     in the published price list, but the existing Born Report row in
--     practice_types may have FK references on live practices. Leaving
--     it active and adding the new Lapor Lahir codes alongside.
-- =====================================================================

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('other_lapor_lahir_under',           'Lapor Lahir (Under)',                          'Birth report registration for foreign nationals born in Indonesia, filed within the standard window (under 60 days Kanim NGR / under 90 days Kanim DPS).', 'other', 2000000, NULL, true),
    ('other_lapor_lahir_up',              'Lapor Lahir (Up)',                             'Birth report registration for foreign nationals born in Indonesia, filed after the standard window (above 60 days Kanim NGR / above 90 days Kanim DPS).',  'other', 4000000, NULL, true),
    ('other_mutation_address_2_kanim',    'Mutation Address 2 Kanim',                     'Update of registered address requiring inter-Kanim (immigration office) transfer.',                                                                                'other', 1000000, NULL, true),
    ('other_created_molina_express',      'Created Molina Express',                       'Express creation of immigration record on the Molina (immigration) database.',                                                                                     'other', 500000,  NULL, true),
    ('other_imta_rptka_only_12mo',        'Process IMTA & RPTKA Only (12 Months)',        'Stand-alone processing of IMTA and RPTKA work permit documents, valid for 12 months.',                                                                            'other', 3500000, NULL, true),
    ('other_imta_rptka_only_6mo_or_less', 'Process IMTA & RPTKA Only (6 Months or Less)', 'Stand-alone processing of IMTA and RPTKA work permit documents, valid for 6 months or less.',                                                                     'other', 6000000, NULL, true),
    ('other_driving_license',             'Driving License',                              'Indonesian driving license (SIM) issuance for foreign nationals.',                                                                                                  'other', 1600000, NULL, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- =====================================================================
-- 11. HARD-DELETE obsolete 2025 entries (owner decision A, 2026-05-06)
--
-- These 7 services are removed from the 2026 published price list and
-- the owner explicitly approved hard-delete (option A in the planning
-- conversation):
--   ACC × 3       — ACC Mutation, ACC Mutation Passport, ACC Boarding Pass
--   MERP 1Y / 2Y  — standalone MERP entries (KITAP+MERP bundles already
--                   include MERP, so the standalone rows became orphans)
--   Cancel combo  — Cancel (RPTKA, IMTA, Wajib Lapor) — replaced by
--                   individual Cancel RPTKA + Cancel Wajib Lapor at
--                   updated 1M prices each
--   Domicilie+SKTT bundle — clients now order SKTT and Domicilie Letter
--                           separately
--   Domicilie Letter — removed from 2026 list entirely
--
-- ⚠️ FK shape: practices has TWO FKs onto practice_types —
--   practices.practice_type_id   → practice_types.id    (integer FK)
--   practices.practice_type_code  → practice_types.code  (text FK)
-- Both are nullable. If any LIVE practice references one of these 8
-- codes via either column, this DELETE FAILS with a foreign key
-- violation and the entire migration rolls back (atomic).
--
-- Preflight verified 2026-05-06 against prod: all 8 codes have ZERO
-- practice references via both FK columns, so the DELETE is safe.
-- If the situation changes between preflight and deploy, the migration
-- fails cleanly and we run the diagnostic SELECT below to enumerate
-- offenders and decide case-by-case (re-assign to a current code or
-- soft-disable that row instead).
--
-- Diagnostic on failure:
--   SELECT id, practice_type_code, practice_type_id, status, created_at
--   FROM practices
--   WHERE practice_type_code = ANY(ARRAY['other_acc_mutation', ...])
--      OR practice_type_id IN (SELECT id FROM practice_types
--                              WHERE code = ANY(ARRAY[...]));
-- =====================================================================

DELETE FROM practice_types WHERE code = ANY(ARRAY[
    'other_acc_mutation',
    'other_acc_mutation_passport',
    'other_acc_boarding_pass',
    'merp_1yr',
    'merp_2yr',
    'other_cancel_rptka_imta_wl',
    'other_domicilie_sktt',
    'other_domicilie'
]::text[]);

-- === ROLLBACK ===
-- Soft-disable the rows added by this migration (DO NOT hard-delete:
-- live practices may already reference them via practice_type_id /
-- practice_type_code FKs once the migration is deployed). Same pattern
-- as migration_148_practice_types_bridging_visa.
--
-- Price-update statements in section 1 are NOT rolled back: reverting a
-- price would require knowing the previous value, which is encoded in
-- migration_066's seed values. If a price change needs to be undone,
-- write a follow-up migration that sets the explicit prior price.
--
-- The HARD-DELETE in section 11 (ACC×3, MERP 1Y/2Y, Cancel combo,
-- Domicilie+SKTT, Domicilie Letter) is NOT rolled back here either.
-- Restoring those rows requires re-running the original INSERT from
-- migration_066. If a rollback is needed, write a follow-up migration
-- that re-INSERTs the 7 codes with their original 2025 values.

UPDATE practice_types SET is_active = false WHERE code = ANY(ARRAY[
    'visa_c8_journalism',
    'visa_c10_speaker',
    'visa_d2_business_1yr',
    'visa_d2_business_2yr',
    'kitas_born',
    'tax_monthly_basic_0_50',
    'tax_monthly_basic_50_100',
    'tax_monthly_basic_100_200',
    'tax_monthly_basic_200_plus',
    'tax_monthly_bundled_0_50',
    'tax_monthly_bundled_50_100',
    'tax_monthly_bundled_100_200',
    'tax_monthly_bundled_200_plus',
    'tax_annual_pkg_a',
    'tax_annual_pkg_b',
    'tax_annual_pkg_c',
    'tax_annual_pkg_d',
    'tax_annual_company_zero',
    'tax_lkpm_yearly',
    'tax_annual_company',
    'tax_annual_personal',
    'tax_annual_personal_addl',
    'tax_npwpd_registration',
    'tax_bpjs_employee',
    'tax_bpjs_insurance',
    'tax_npwp_personal_coretax',
    'tax_update_data_coretax',
    'tax_efin_application',
    'tax_close_pma_company',
    'other_lapor_lahir_under',
    'other_lapor_lahir_up',
    'other_mutation_address_2_kanim',
    'other_created_molina_express',
    'other_imta_rptka_only_12mo',
    'other_imta_rptka_only_6mo_or_less',
    'other_driving_license'
]::text[]);
