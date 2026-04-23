"""Migration 066: Populate practice_types with all 62 services from official pricing.

Replaces the 13 generic practice_types with the full service catalog from
bali_zero_official_prices_2025.json, so team members can select the exact
service when creating a new process.

Old generic entries (visa, kitas, etc.) are soft-deactivated (is_active=false)
and all new specific services are inserted.
"""

import asyncio
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

# All services from bali_zero_official_prices_2025.json mapped to practice_types rows.
# code: unique snake_case identifier
# name: display name (as in the pricing JSON)
# category: maps to JSON category key
# base_price: in IDR (numeric, parsed from "X.XXX.XXX IDR" format)
# typical_duration_days: estimated processing days (NULL if unknown)
# required_documents: placeholder array

SERVICES = [
    # === single_entry_visas ===
    {"code": "visa_c1_tourism", "name": "C1 Tourism Visa", "category": "single_entry_visa", "base_price": 2300000, "duration": None, "notes": "Single entry, 60 days"},
    {"code": "visa_c2_business", "name": "C2 Business Visa", "category": "single_entry_visa", "base_price": 3600000, "duration": None, "notes": "Single entry, 60 days"},
    {"code": "visa_c7_music_art", "name": "C7A&B Music/Art Visa", "category": "single_entry_visa", "base_price": 4500000, "duration": None, "notes": "Including Urgent"},
    {"code": "visa_c18_work_trial", "name": "C18 Work Trial Visa", "category": "single_entry_visa", "base_price": 5500000, "duration": 90, "notes": "Work trial / skill assessment"},
    {"code": "visa_c22_internship_60d", "name": "C22A&B Internship (60 Days)", "category": "single_entry_visa", "base_price": 4800000, "duration": 60, "notes": ""},
    {"code": "visa_c22_internship_180d", "name": "C22A&B Internship (180 Days)", "category": "single_entry_visa", "base_price": 5800000, "duration": 180, "notes": ""},

    # === visa_extensions ===
    {"code": "ext_c1_tourism", "name": "C1 Tourism Extension", "category": "visa_extension", "base_price": 1700000, "duration": 30, "notes": "+30 days"},

    # === multiple_entry_visas ===
    {"code": "visa_d1_tourism_1yr", "name": "D1 Tourism (1 Year)", "category": "multiple_entry_visa", "base_price": 6000000, "duration": 365, "notes": ""},
    {"code": "visa_d1_tourism_2yr", "name": "D1 Tourism (2 Years)", "category": "multiple_entry_visa", "base_price": 8000000, "duration": 730, "notes": ""},
    {"code": "visa_d1_tourism_5yr", "name": "D1 Tourism (5 Years)", "category": "multiple_entry_visa", "base_price": 14000000, "duration": 1825, "notes": ""},
    {"code": "visa_d12_business_1yr", "name": "D12 Business Investigation (1 Year)", "category": "multiple_entry_visa", "base_price": 7500000, "duration": 365, "notes": ""},
    {"code": "visa_d12_business_2yr", "name": "D12 Business Investigation (2 Years)", "category": "multiple_entry_visa", "base_price": 10000000, "duration": 730, "notes": ""},

    # === kitas_permits ===
    {"code": "kitas_working_offshore", "name": "Working KITAS (Offshore)", "category": "kitas", "base_price": 34500000, "duration": 365, "notes": ""},
    {"code": "kitas_working_onshore", "name": "Working KITAS (Altus/Onshore)", "category": "kitas", "base_price": 36000000, "duration": 365, "notes": ""},
    {"code": "kitas_working_extend", "name": "Working KITAS (Extend)", "category": "kitas", "base_price": 31500000, "duration": None, "notes": ""},
    {"code": "kitas_investor_2yr_offshore", "name": "Investor KITAS 2 Years (Offshore)", "category": "kitas", "base_price": 17000000, "duration": 730, "notes": ""},
    {"code": "kitas_investor_2yr_onshore", "name": "Investor KITAS 2 Years (Altus/Onshore)", "category": "kitas", "base_price": 19000000, "duration": 730, "notes": ""},
    {"code": "kitas_investor_2yr_extend", "name": "Investor KITAS 2 Years (Extend)", "category": "kitas", "base_price": 18000000, "duration": None, "notes": ""},
    {"code": "kitas_spouse_1yr_offshore", "name": "Spouse 1 Year (Offshore)", "category": "kitas", "base_price": 11000000, "duration": 365, "notes": ""},
    {"code": "kitas_spouse_1yr_onshore", "name": "Spouse 1 Year (Altus/Onshore)", "category": "kitas", "base_price": 13500000, "duration": 365, "notes": ""},
    {"code": "kitas_spouse_1yr_extend", "name": "Spouse 1 Year (Extend)", "category": "kitas", "base_price": 9000000, "duration": None, "notes": ""},
    {"code": "kitas_spouse_2yr_offshore", "name": "Spouse 2 Years (Offshore)", "category": "kitas", "base_price": 15000000, "duration": 730, "notes": ""},
    {"code": "kitas_spouse_2yr_onshore", "name": "Spouse 2 Years (Altus/Onshore)", "category": "kitas", "base_price": 18000000, "duration": 730, "notes": ""},
    {"code": "kitas_spouse_2yr_extend", "name": "Spouse 2 Years (Extend)", "category": "kitas", "base_price": 15000000, "duration": None, "notes": ""},
    {"code": "kitas_dependent_1yr_offshore", "name": "Dependent 1 Year (Offshore)", "category": "kitas", "base_price": 11000000, "duration": 365, "notes": ""},
    {"code": "kitas_dependent_1yr_onshore", "name": "Dependent 1 Year (Altus/Onshore)", "category": "kitas", "base_price": 13500000, "duration": 365, "notes": ""},
    {"code": "kitas_dependent_1yr_extend", "name": "Dependent 1 Year (Extend)", "category": "kitas", "base_price": 9000000, "duration": None, "notes": ""},
    {"code": "kitas_dependent_2yr_offshore", "name": "Dependent 2 Years (Offshore)", "category": "kitas", "base_price": 15000000, "duration": 730, "notes": ""},
    {"code": "kitas_dependent_2yr_onshore", "name": "Dependent 2 Years (Altus/Onshore)", "category": "kitas", "base_price": 18000000, "duration": 730, "notes": ""},
    {"code": "kitas_dependent_2yr_extend", "name": "Dependent 2 Years (Extend)", "category": "kitas", "base_price": 15000000, "duration": None, "notes": ""},
    {"code": "kitas_remote_worker_offshore", "name": "E33G Remote Worker (Offshore)", "category": "kitas", "base_price": 13000000, "duration": None, "notes": "Including Urgent"},
    {"code": "kitas_remote_worker_onshore", "name": "E33G Remote Worker (Altus/Onshore)", "category": "kitas", "base_price": 14000000, "duration": None, "notes": ""},
    {"code": "kitas_remote_worker_extend", "name": "E33G Remote Worker (Extend)", "category": "kitas", "base_price": 10000000, "duration": None, "notes": ""},
    {"code": "kitas_freelance_offshore", "name": "Freelance E23 (Offshore)", "category": "kitas", "base_price": 25800000, "duration": 180, "notes": ""},
    {"code": "kitas_freelance_onshore", "name": "Freelance E23 (Altus/Onshore)", "category": "kitas", "base_price": 27500000, "duration": 180, "notes": ""},
    {"code": "kitas_retirement_offshore", "name": "Retirement (Offshore)", "category": "kitas", "base_price": 14000000, "duration": None, "notes": ""},
    {"code": "kitas_retirement_onshore", "name": "Retirement (Altus/Onshore)", "category": "kitas", "base_price": 16000000, "duration": None, "notes": ""},
    {"code": "kitas_retirement_extend", "name": "Retirement (Extend)", "category": "kitas", "base_price": 10000000, "duration": None, "notes": ""},

    # === kitap_permits ===
    {"code": "kitap_retirement_merp", "name": "Retirement KITAP + MERP", "category": "kitap", "base_price": 45000000, "duration": None, "notes": ""},
    {"code": "kitap_investor_merp", "name": "Investor KITAP + MERP", "category": "kitap", "base_price": 55000000, "duration": None, "notes": "Expedited processing available"},
    {"code": "kitap_dependent_merp", "name": "Dependent KITAP MERP", "category": "kitap", "base_price": 33000000, "duration": None, "notes": "Expedited processing available"},
    {"code": "merp_1yr", "name": "MERP 1 Year", "category": "kitap", "base_price": 4000000, "duration": 365, "notes": ""},
    {"code": "merp_2yr", "name": "MERP 2 Year", "category": "kitap", "base_price": 5000000, "duration": 730, "notes": ""},

    # === company_services ===
    {"code": "company_pt_pma", "name": "New Company (PT PMA)", "category": "company", "base_price": 20000000, "duration": None, "notes": ""},
    {"code": "company_virtual_office", "name": "Virtual Office", "category": "company", "base_price": 5000000, "duration": None, "notes": "Solo se il cliente NON ha ancora una sede commerciale propria"},
    {"code": "company_revision", "name": "Revision Company", "category": "company", "base_price": None, "duration": None, "notes": "Contact for quote"},
    {"code": "company_revision_akta", "name": "Revision Company (Akta Perubahan)", "category": "company", "base_price": None, "duration": None, "notes": "Richiesto se cambia indirizzo sede, direttori, attività"},

    # === other_process ===
    {"code": "other_reset_molina", "name": "Reset Molina", "category": "other", "base_price": 1000000, "duration": None, "notes": "Plus 400k urgent"},
    {"code": "other_skck", "name": "SKCK", "category": "other", "base_price": 2000000, "duration": None, "notes": ""},
    {"code": "other_sktt", "name": "SKTT", "category": "other", "base_price": 1500000, "duration": None, "notes": ""},
    {"code": "other_domicilie", "name": "Domicilie Letter", "category": "other", "base_price": 800000, "duration": None, "notes": ""},
    {"code": "other_domicilie_sktt", "name": "Domicilie + SKTT", "category": "other", "base_price": 1600000, "duration": None, "notes": ""},
    {"code": "other_epo", "name": "EPO (Exit Permit Only)", "category": "other", "base_price": 700000, "duration": None, "notes": "Plus 300k urgent"},
    {"code": "other_erp", "name": "ERP (Exit Re-entry Permit)", "category": "other", "base_price": 800000, "duration": None, "notes": "Plus 500k urgent"},
    {"code": "other_mutation_passport", "name": "Mutation Passport", "category": "other", "base_price": 500000, "duration": None, "notes": "Plus 350k urgent"},
    {"code": "other_mutation_address", "name": "Mutation Address", "category": "other", "base_price": 500000, "duration": None, "notes": ""},
    {"code": "other_acc_mutation", "name": "ACC Mutation", "category": "other", "base_price": 1000000, "duration": None, "notes": ""},
    {"code": "other_acc_mutation_passport", "name": "ACC Mutation Passport", "category": "other", "base_price": 1000000, "duration": None, "notes": ""},
    {"code": "other_acc_boarding_pass", "name": "ACC Boarding Pass", "category": "other", "base_price": 1200000, "duration": None, "notes": ""},
    {"code": "other_born_report", "name": "Born Report", "category": "other", "base_price": 4000000, "duration": None, "notes": ""},
    {"code": "other_passport_5yr", "name": "Passport 5 Years", "category": "other", "base_price": 1300000, "duration": None, "notes": ""},
    {"code": "other_passport_10yr", "name": "Passport 10 Years", "category": "other", "base_price": 2000000, "duration": None, "notes": ""},
    {"code": "other_epassport_5yr", "name": "Electronic Passport 5 Years", "category": "other", "base_price": 2000000, "duration": None, "notes": ""},
    {"code": "other_epassport_10yr", "name": "Electronic Passport 10 Years", "category": "other", "base_price": 2500000, "duration": None, "notes": ""},
    {"code": "other_cancel_rptka", "name": "Cancel RPTKA", "category": "other", "base_price": 500000, "duration": None, "notes": ""},
    {"code": "other_cancel_wajib_lapor", "name": "Cancel Wajib Lapor", "category": "other", "base_price": 500000, "duration": None, "notes": ""},
    {"code": "other_cancel_rptka_imta_wl", "name": "Cancel (RPTKA, IMTA, Wajib Lapor)", "category": "other", "base_price": 3500000, "duration": None, "notes": ""},

    # === urgent_services ===
    {"code": "urgent_1_day", "name": "Urgent 1 Hari", "category": "urgent", "base_price": 3000000, "duration": 1, "notes": ""},
    {"code": "urgent_2_days", "name": "Urgent 2 Hari", "category": "urgent", "base_price": 2500000, "duration": 2, "notes": ""},
    {"code": "urgent_3_days", "name": "Urgent 3 Hari", "category": "urgent", "base_price": 1000000, "duration": 3, "notes": ""},

    # === tax (not in JSON but needed) ===
    {"code": "tax_registration", "name": "Tax Registration (NPWP)", "category": "tax", "base_price": 3000000, "duration": None, "notes": "NPWP registration and reporting"},
    {"code": "tax_annual_reporting", "name": "Annual Tax Reporting", "category": "tax", "base_price": 3000000, "duration": None, "notes": "SPT Tahunan filing"},
]


async def upgrade(conn: asyncpg.Connection) -> None:
    """Deactivate old generic entries and insert all specific services."""
    logger.info("Migration 066: Populating practice_types with full service catalog")

    # 1. Deactivate old generic entries (keep them for FK references on existing practices)
    old_codes = [
        "visa", "extension_visa", "kitas", "extension_kitas", "tax",
        "new_pt", "revision_pt", "accessories",
        "pt_pma_setup", "property_purchase", "tax_consulting",
        "kitas_application", "kitap_application",
    ]
    deactivated = await conn.execute(
        "UPDATE practice_types SET is_active = false WHERE code = ANY($1::text[])",
        old_codes,
    )
    logger.info(f"Deactivated old practice_types: {deactivated}")

    # 2. Insert new specific services
    inserted = 0
    for svc in SERVICES:
        try:
            await conn.execute(
                """
                INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, true)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    base_price = EXCLUDED.base_price,
                    typical_duration_days = EXCLUDED.typical_duration_days,
                    is_active = true,
                    updated_at = CURRENT_TIMESTAMP
                """,
                svc["code"],
                svc["name"],
                svc["notes"] or None,
                svc["category"],
                svc["base_price"],
                svc["duration"],
            )
            inserted += 1
        except Exception as e:
            logger.error(f"Failed to insert {svc['code']}: {e}")

    logger.info(f"Migration 066 complete: {inserted} services inserted/updated")


async def downgrade(conn: asyncpg.Connection) -> None:
    """Remove new services and reactivate old generic entries."""
    new_codes = [svc["code"] for svc in SERVICES]
    await conn.execute(
        "DELETE FROM practice_types WHERE code = ANY($1::text[])",
        new_codes,
    )
    await conn.execute(
        "UPDATE practice_types SET is_active = true"
    )
    logger.info("Migration 066 downgraded: removed new services, reactivated old entries")


async def run() -> None:
    """Run migration standalone."""
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable",
    )
    conn = await asyncpg.connect(db_url)
    try:
        await upgrade(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
