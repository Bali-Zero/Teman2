"""
Migration 069: Align HR bonus rates with practice_types codes + add single entry visa rates.

Fixes:
- Bonus rates in production used free-text codes with spaces (e.g. 'company pt pma')
  but practice_types.code uses underscores (e.g. 'company_pt_pma').
- Adds missing single entry C visas (Rp 100.000 each) and D12 multiple entry (Rp 150.000).
- Updates VOA extension code from 'visa' to 'ext_c1_tourism' (Rp 10.000).

This migration is idempotent (ON CONFLICT DO UPDATE).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


UPGRADE_SQL = """
-- ============================================
-- HR BONUS RATES ALIGNMENT (Migration 069)
-- ============================================

-- 1. Fix existing rates: remap free-text codes to practice_types.code
-- Using UPDATE with WHERE to only change if the old code exists

UPDATE hr_bonus_rates SET practice_type_code = 'company_pt_pma', updated_at = NOW()
WHERE practice_type_code = 'company pt pma';

UPDATE hr_bonus_rates SET practice_type_code = 'company_revision', updated_at = NOW()
WHERE practice_type_code = 'company revision';

UPDATE hr_bonus_rates SET practice_type_code = 'company_revision_akta', updated_at = NOW()
WHERE practice_type_code = 'company revision akta';

UPDATE hr_bonus_rates SET practice_type_code = 'kitap_retirement_merp', updated_at = NOW()
WHERE practice_type_code = 'kitap retirement merp';

UPDATE hr_bonus_rates SET practice_type_code = 'kitap_investor_merp', updated_at = NOW()
WHERE practice_type_code = 'kitap investor merp';

UPDATE hr_bonus_rates SET practice_type_code = 'kitap_dependent_merp', updated_at = NOW()
WHERE practice_type_code = 'kitap dependent merp';

UPDATE hr_bonus_rates SET practice_type_code = 'kitas_dependent_1yr_extend', updated_at = NOW()
WHERE practice_type_code = 'kitas dependent 1yr extend';

UPDATE hr_bonus_rates SET practice_type_code = 'kitas_dependent_1yr_offshore', updated_at = NOW()
WHERE practice_type_code = 'kitas dependent 1yr offshore';

UPDATE hr_bonus_rates SET practice_type_code = 'kitas_dependent_1yr_onshore', updated_at = NOW()
WHERE practice_type_code = 'kitas dependent 1yr onshore';

-- 'extension kitas' → match existing practice_types code 'extension_kitas' (from migration_044)
-- or the newer code pattern — keep as is since it exists in practice_types

UPDATE hr_bonus_rates SET practice_type_code = 'extension_kitas', updated_at = NOW()
WHERE practice_type_code = 'extension kitas';

-- 'kitap application' → no exact match in practice_types, keep as custom
UPDATE hr_bonus_rates SET practice_type_code = 'kitap_application', updated_at = NOW()
WHERE practice_type_code = 'kitap application';

-- 'kitas application' → duplicate of 'kitas', deactivate
UPDATE hr_bonus_rates SET is_active = FALSE, notes = 'Duplicate of kitas, deactivated by migration 069', updated_at = NOW()
WHERE practice_type_code = 'kitas application';

-- 'visa' (VOA extension Rp 10.000) → remap to ext_c1_tourism
UPDATE hr_bonus_rates SET practice_type_code = 'ext_c1_tourism', notes = 'VOA (Visa on Arrival) extension', updated_at = NOW()
WHERE practice_type_code = 'visa' AND amount_idr = 10000;

-- 2. Add missing single entry C visa rates (all Rp 100.000)
INSERT INTO hr_bonus_rates (practice_type_code, amount_idr, effective_from, is_active, notes)
VALUES
    ('visa_c1_tourism',          100000, '2026-01-01', TRUE, 'C1 Tourism single entry'),
    ('visa_c2_business',         100000, '2026-01-01', TRUE, 'C2 Business single entry'),
    ('visa_c7_music_art',        100000, '2026-01-01', TRUE, 'C7A&B Music/Art single entry'),
    ('visa_c18_work_trial',      100000, '2026-01-01', TRUE, 'C18 Work Trial single entry'),
    ('visa_c22_internship_60d',  100000, '2026-01-01', TRUE, 'C22 Internship 60 days'),
    ('visa_c22_internship_180d', 100000, '2026-01-01', TRUE, 'C22 Internship 180 days')
ON CONFLICT (practice_type_code) DO UPDATE SET
    amount_idr = EXCLUDED.amount_idr,
    is_active = EXCLUDED.is_active,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- 3. Add missing multiple entry D12 rates (Rp 150.000)
INSERT INTO hr_bonus_rates (practice_type_code, amount_idr, effective_from, is_active, notes)
VALUES
    ('visa_d12_business_1yr', 150000, '2026-01-01', TRUE, 'D12 Business Investigation 1 Year'),
    ('visa_d12_business_2yr', 150000, '2026-01-01', TRUE, 'D12 Business Investigation 2 Years')
ON CONFLICT (practice_type_code) DO UPDATE SET
    amount_idr = EXCLUDED.amount_idr,
    is_active = EXCLUDED.is_active,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- 4. Also fix bonus_ledger entries that reference old codes (cascade the rename)
UPDATE hr_bonus_ledger SET practice_type_code = 'company_pt_pma' WHERE practice_type_code = 'company pt pma';
UPDATE hr_bonus_ledger SET practice_type_code = 'company_revision' WHERE practice_type_code = 'company revision';
UPDATE hr_bonus_ledger SET practice_type_code = 'company_revision_akta' WHERE practice_type_code = 'company revision akta';
UPDATE hr_bonus_ledger SET practice_type_code = 'extension_kitas' WHERE practice_type_code = 'extension kitas';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitap_retirement_merp' WHERE practice_type_code = 'kitap retirement merp';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitap_investor_merp' WHERE practice_type_code = 'kitap investor merp';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitap_dependent_merp' WHERE practice_type_code = 'kitap dependent merp';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitap_application' WHERE practice_type_code = 'kitap application';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitas_dependent_1yr_extend' WHERE practice_type_code = 'kitas dependent 1yr extend';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitas_dependent_1yr_offshore' WHERE practice_type_code = 'kitas dependent 1yr offshore';
UPDATE hr_bonus_ledger SET practice_type_code = 'kitas_dependent_1yr_onshore' WHERE practice_type_code = 'kitas dependent 1yr onshore';
UPDATE hr_bonus_ledger SET practice_type_code = 'ext_c1_tourism' WHERE practice_type_code = 'visa';
"""


DOWNGRADE_SQL = """
-- Reverse code renames (best effort — original free-text codes)
UPDATE hr_bonus_rates SET practice_type_code = 'company pt pma' WHERE practice_type_code = 'company_pt_pma';
UPDATE hr_bonus_rates SET practice_type_code = 'company revision' WHERE practice_type_code = 'company_revision';
UPDATE hr_bonus_rates SET practice_type_code = 'company revision akta' WHERE practice_type_code = 'company_revision_akta';
UPDATE hr_bonus_rates SET practice_type_code = 'extension kitas' WHERE practice_type_code = 'extension_kitas';
UPDATE hr_bonus_rates SET practice_type_code = 'kitap retirement merp' WHERE practice_type_code = 'kitap_retirement_merp';
UPDATE hr_bonus_rates SET practice_type_code = 'kitap investor merp' WHERE practice_type_code = 'kitap_investor_merp';
UPDATE hr_bonus_rates SET practice_type_code = 'kitap dependent merp' WHERE practice_type_code = 'kitap_dependent_merp';
UPDATE hr_bonus_rates SET practice_type_code = 'kitap application' WHERE practice_type_code = 'kitap_application';
UPDATE hr_bonus_rates SET practice_type_code = 'kitas dependent 1yr extend' WHERE practice_type_code = 'kitas_dependent_1yr_extend';
UPDATE hr_bonus_rates SET practice_type_code = 'kitas dependent 1yr offshore' WHERE practice_type_code = 'kitas_dependent_1yr_offshore';
UPDATE hr_bonus_rates SET practice_type_code = 'kitas dependent 1yr onshore' WHERE practice_type_code = 'kitas_dependent_1yr_onshore';
UPDATE hr_bonus_rates SET practice_type_code = 'visa' WHERE practice_type_code = 'ext_c1_tourism' AND amount_idr = 10000;

-- Remove added rates
DELETE FROM hr_bonus_rates WHERE practice_type_code IN (
    'visa_c1_tourism', 'visa_c2_business', 'visa_c7_music_art',
    'visa_c18_work_trial', 'visa_c22_internship_60d', 'visa_c22_internship_180d',
    'visa_d12_business_1yr', 'visa_d12_business_2yr'
);

-- Reactivate duplicate
UPDATE hr_bonus_rates SET is_active = TRUE WHERE practice_type_code = 'kitas application';
"""


async def upgrade(conn: Any) -> None:
    """Align bonus rates with practice_types codes + add visa rates."""
    await conn.execute(UPGRADE_SQL)
    logger.info("Migration 069: HR bonus rates aligned + 8 visa rates added")


async def downgrade(conn: Any) -> None:
    """Reverse bonus rate alignment."""
    await conn.execute(DOWNGRADE_SQL)
    logger.info("Migration 069: HR bonus rates alignment reversed")
