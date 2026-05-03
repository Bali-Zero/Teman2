"""
Apply migration 033: CRM Enhanced Client Profile
"""

import asyncio
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg


async def run_migration():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    print("=== Migration 033: CRM Enhanced Client Profile ===\n")

    # 1. Add columns to clients table
    print("1. Adding columns to clients table...")
    client_cols = [
        ("avatar_url", "TEXT"),
        ("google_drive_folder_id", "VARCHAR(100)"),
        ("date_of_birth", "DATE"),
        ("passport_expiry", "DATE"),
    ]

    for col, typ in client_cols:
        try:
            await conn.execute(f"ALTER TABLE clients ADD COLUMN IF NOT EXISTS {col} {typ}")
            print(f"   ✅ clients.{col}")
        except Exception as e:
            print(f"   ⚠️  clients.{col}: {e}")

    # 2. Create client_family_members table
    print("\n2. Creating client_family_members table...")
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_family_members (
                id SERIAL PRIMARY KEY,
                client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                full_name VARCHAR(255) NOT NULL,
                relationship VARCHAR(50) NOT NULL,
                date_of_birth DATE,
                nationality VARCHAR(100),
                passport_number VARCHAR(100),
                passport_expiry DATE,
                current_visa_type VARCHAR(50),
                visa_expiry DATE,
                email VARCHAR(255),
                phone VARCHAR(50),
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_by VARCHAR(255)
            )
        """
        )
        print("   ✅ client_family_members table created")
    except Exception as e:
        print(f"   ⚠️  client_family_members: {e}")

    # 3. Create family member indexes
    print("\n3. Creating family member indexes...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_family_members_client_id ON client_family_members(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_family_members_relationship ON client_family_members(relationship)",
        "CREATE INDEX IF NOT EXISTS idx_family_members_visa_expiry ON client_family_members(visa_expiry)",
        "CREATE INDEX IF NOT EXISTS idx_family_members_passport_expiry ON client_family_members(passport_expiry)",
    ]
    for idx in indexes:
        try:
            await conn.execute(idx)
            print("   ✅ Index created")
        except Exception as e:
            print(f"   ⚠️  Index: {e}")

    # 4. Add columns to documents table
    print("\n4. Adding columns to documents table...")
    doc_cols = [
        ("document_category", "VARCHAR(50)"),
        ("family_member_id", "INT REFERENCES client_family_members(id) ON DELETE SET NULL"),
        ("google_drive_file_url", "TEXT"),
        ("is_archived", "BOOLEAN DEFAULT false"),
    ]

    for col, typ in doc_cols:
        try:
            await conn.execute(f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col} {typ}")
            print(f"   ✅ documents.{col}")
        except Exception as e:
            print(f"   ⚠️  documents.{col}: {e}")

    # 5. Create document indexes
    print("\n5. Creating document indexes...")
    doc_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(document_category)",
        "CREATE INDEX IF NOT EXISTS idx_documents_family_member ON documents(family_member_id)",
        "CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date)",
        "CREATE INDEX IF NOT EXISTS idx_documents_archived ON documents(is_archived)",
    ]
    for idx in doc_indexes:
        try:
            await conn.execute(idx)
            print("   ✅ Document index created")
        except Exception as e:
            print(f"   ⚠️  Document index: {e}")

    # 6. Create document_categories table
    print("\n6. Creating document_categories table...")
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_categories (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                category_group VARCHAR(50) NOT NULL,
                description TEXT,
                required_for JSONB DEFAULT '[]'::jsonb,
                has_expiry BOOLEAN DEFAULT false,
                sort_order INT DEFAULT 0,
                active BOOLEAN DEFAULT true
            )
        """
        )
        print("   ✅ document_categories table created")
    except Exception as e:
        print(f"   ⚠️  document_categories: {e}")

    # 7. Seed document categories
    print("\n7. Seeding document categories...")
    categories = [
        # Immigration Documents
        ("passport", "Passport", "immigration", True, 1),
        ("kitas", "KITAS (Kartu Izin Tinggal Terbatas)", "immigration", True, 2),
        ("kitap", "KITAP (Kartu Izin Tinggal Tetap)", "immigration", True, 3),
        ("visa_kunjungan", "Visa Kunjungan (Visit Visa)", "immigration", True, 4),
        ("voa", "Visa on Arrival", "immigration", True, 5),
        ("rptka", "RPTKA (Work Permit)", "immigration", True, 8),
        ("imta", "IMTA (Work Permit Card)", "immigration", True, 9),
        ("merp", "MERP (Exit Re-entry Permit)", "immigration", True, 10),
        ("sponsor_letter", "Sponsor Letter", "immigration", False, 11),
        ("domicile_letter", "Domicile Letter (SKTT)", "immigration", True, 12),
        # PT PMA Documents
        ("nib", "NIB (Nomor Induk Berusaha)", "pma", True, 20),
        ("akta_pendirian", "Akta Pendirian (Deed of Establishment)", "pma", False, 21),
        ("sk_kemenkumham", "SK Kemenkumham (Legal Approval)", "pma", False, 22),
        ("npwp_company", "NPWP Perusahaan (Company Tax ID)", "pma", False, 23),
        ("surat_domisili", "Surat Domisili (Company Domicile)", "pma", True, 24),
        ("oss_certificate", "OSS Certificate", "pma", False, 25),
        # Tax Documents
        ("npwp", "NPWP (Personal Tax ID)", "tax", False, 30),
        ("efin", "EFIN (Electronic Filing ID)", "tax", False, 31),
        ("spt_tahunan", "SPT Tahunan (Annual Tax Return)", "tax", False, 32),
        ("lkpm", "LKPM (Investment Report)", "tax", True, 34),
        ("bpjs_tk", "BPJS Ketenagakerjaan", "tax", True, 35),
        ("bpjs_kes", "BPJS Kesehatan", "tax", True, 36),
        # Personal Documents
        ("photo", "Photo/Avatar", "personal", False, 40),
        ("cv", "CV/Resume", "personal", False, 41),
        ("diploma", "Diploma/Certificate", "personal", False, 42),
        ("marriage_cert", "Marriage Certificate", "personal", False, 43),
        ("birth_cert", "Birth Certificate", "personal", False, 44),
        ("police_clearance", "Police Clearance (SKCK)", "personal", True, 45),
        # Other
        ("contract", "Contract/Agreement", "other", True, 50),
        ("invoice", "Invoice", "other", False, 51),
        ("receipt", "Receipt/Payment Proof", "other", False, 52),
        ("other", "Other Document", "other", False, 99),
    ]

    for code, name, category_group, has_expiry, sort_order in categories:
        try:
            await conn.execute(
                """
                INSERT INTO document_categories (code, name, category_group, has_expiry, sort_order)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (code) DO NOTHING
            """,
                code,
                name,
                category_group,
                has_expiry,
                sort_order,
            )
        except Exception as e:
            print(f"   ⚠️  Category {code}: {e}")

    print(f"   ✅ Seeded {len(categories)} document categories")

    # 8. Create views
    print("\n8. Creating views...")

    # Expiry alerts view
    try:
        await conn.execute(
            """
            CREATE OR REPLACE VIEW client_expiry_alerts_view AS
            SELECT
                'client' as entity_type,
                c.id as entity_id,
                c.full_name as entity_name,
                c.id as client_id,
                c.full_name as client_name,
                'passport' as document_type,
                c.passport_expiry as expiry_date,
                c.passport_expiry - CURRENT_DATE as days_until_expiry,
                CASE
                    WHEN c.passport_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN c.passport_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN c.passport_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color,
                c.assigned_to
            FROM clients c
            WHERE c.passport_expiry IS NOT NULL
              AND c.status = 'active'

            UNION ALL

            SELECT
                'family_member' as entity_type,
                fm.id as entity_id,
                fm.full_name as entity_name,
                fm.client_id,
                c.full_name as client_name,
                'passport' as document_type,
                fm.passport_expiry as expiry_date,
                fm.passport_expiry - CURRENT_DATE as days_until_expiry,
                CASE
                    WHEN fm.passport_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN fm.passport_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN fm.passport_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color,
                c.assigned_to
            FROM client_family_members fm
            JOIN clients c ON fm.client_id = c.id
            WHERE fm.passport_expiry IS NOT NULL

            UNION ALL

            SELECT
                'family_member' as entity_type,
                fm.id as entity_id,
                fm.full_name as entity_name,
                fm.client_id,
                c.full_name as client_name,
                'visa' as document_type,
                fm.visa_expiry as expiry_date,
                fm.visa_expiry - CURRENT_DATE as days_until_expiry,
                CASE
                    WHEN fm.visa_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN fm.visa_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN fm.visa_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color,
                c.assigned_to
            FROM client_family_members fm
            JOIN clients c ON fm.client_id = c.id
            WHERE fm.visa_expiry IS NOT NULL

            UNION ALL

            SELECT
                'document' as entity_type,
                d.id as entity_id,
                d.document_type as entity_name,
                d.client_id,
                c.full_name as client_name,
                d.document_type,
                d.expiry_date,
                d.expiry_date - CURRENT_DATE as days_until_expiry,
                CASE
                    WHEN d.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color,
                c.assigned_to
            FROM documents d
            JOIN clients c ON d.client_id = c.id
            WHERE d.expiry_date IS NOT NULL
              AND d.status != 'rejected'
              AND (d.is_archived IS NULL OR d.is_archived = false)
        """
        )
        print("   ✅ client_expiry_alerts_view created")
    except Exception as e:
        print(f"   ⚠️  View: {e}")

    await conn.close()
    print("\n=== Migration 033 completed! ===")


if __name__ == "__main__":
    asyncio.run(run_migration())
