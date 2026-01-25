-- ================================================
-- ZANTARA CRM - Enhanced Client Profile
-- Migration 033: Family Members, Documents, Google Drive Integration
-- Created: 2026-01-02
-- ================================================

-- ================================================
-- 1. ENHANCE CLIENTS TABLE
-- ================================================

-- Add avatar_url column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'avatar_url'
    ) THEN
        ALTER TABLE clients ADD COLUMN avatar_url TEXT;
        RAISE NOTICE 'Added avatar_url column to clients table';
    END IF;
END $$;

-- Add google_drive_folder_id column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'google_drive_folder_id'
    ) THEN
        ALTER TABLE clients ADD COLUMN google_drive_folder_id VARCHAR(100);
        RAISE NOTICE 'Added google_drive_folder_id column to clients table';
    END IF;
END $$;

-- Add date_of_birth column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'date_of_birth'
    ) THEN
        ALTER TABLE clients ADD COLUMN date_of_birth DATE;
        RAISE NOTICE 'Added date_of_birth column to clients table';
    END IF;
END $$;

-- Add passport_expiry column (important for immigration!)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'passport_expiry'
    ) THEN
        ALTER TABLE clients ADD COLUMN passport_expiry DATE;
        RAISE NOTICE 'Added passport_expiry column to clients table';
    END IF;
END $$;

-- Add company_name column if missing (some clients have PMA)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'company_name'
    ) THEN
        ALTER TABLE clients ADD COLUMN company_name VARCHAR(255);
        RAISE NOTICE 'Added company_name column to clients table';
    END IF;
END $$;

-- ================================================
-- 2. FAMILY MEMBERS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS client_family_members (
    id SERIAL PRIMARY KEY,

    -- Relation to client
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Family member info
    full_name VARCHAR(255) NOT NULL,
    relationship VARCHAR(50) NOT NULL, -- 'spouse', 'child', 'parent', 'sibling', 'other'
    date_of_birth DATE,
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    passport_expiry DATE,

    -- Immigration status
    current_visa_type VARCHAR(50), -- 'KITAS', 'KITAP', 'VOA', 'C1', 'none'
    visa_expiry DATE,

    -- Contact (for spouse mainly)
    email VARCHAR(255),
    phone VARCHAR(50),

    -- Notes
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_family_members_client_id ON client_family_members(client_id);
CREATE INDEX IF NOT EXISTS idx_family_members_relationship ON client_family_members(relationship);
CREATE INDEX IF NOT EXISTS idx_family_members_visa_expiry ON client_family_members(visa_expiry);
CREATE INDEX IF NOT EXISTS idx_family_members_passport_expiry ON client_family_members(passport_expiry);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_family_members_updated_at ON client_family_members;
CREATE TRIGGER update_family_members_updated_at BEFORE UPDATE ON client_family_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ================================================
-- 3. ENHANCE DOCUMENTS TABLE
-- ================================================

-- Add document_category column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'document_category'
    ) THEN
        ALTER TABLE documents ADD COLUMN document_category VARCHAR(50);
        RAISE NOTICE 'Added document_category column to documents table';
    END IF;
END $$;

-- Add family_member_id for documents that belong to family members
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'family_member_id'
    ) THEN
        ALTER TABLE documents ADD COLUMN family_member_id INT REFERENCES client_family_members(id) ON DELETE SET NULL;
        RAISE NOTICE 'Added family_member_id column to documents table';
    END IF;
END $$;

-- Add google_drive_file_url column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'google_drive_file_url'
    ) THEN
        ALTER TABLE documents ADD COLUMN google_drive_file_url TEXT;
        RAISE NOTICE 'Added google_drive_file_url column to documents table';
    END IF;
END $$;

-- Add is_archived column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'is_archived'
    ) THEN
        ALTER TABLE documents ADD COLUMN is_archived BOOLEAN DEFAULT false;
        RAISE NOTICE 'Added is_archived column to documents table';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(document_category);
CREATE INDEX IF NOT EXISTS idx_documents_family_member ON documents(family_member_id);
CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_documents_archived ON documents(is_archived);

-- ================================================
-- 4. DOCUMENT CATEGORIES REFERENCE
-- ================================================
CREATE TABLE IF NOT EXISTS document_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    category_group VARCHAR(50) NOT NULL, -- 'immigration', 'pma', 'tax', 'personal', 'other'
    description TEXT,
    required_for JSONB DEFAULT '[]'::jsonb, -- ['kitas', 'pt_pma', 'tax_filing']
    has_expiry BOOLEAN DEFAULT false,
    sort_order INT DEFAULT 0,
    active BOOLEAN DEFAULT true
);

-- Insert standard document categories
INSERT INTO document_categories (code, name, category_group, has_expiry, sort_order) VALUES
    -- Immigration Documents
    ('passport', 'Passport', 'immigration', true, 1),
    ('kitas', 'KITAS (Kartu Izin Tinggal Terbatas)', 'immigration', true, 2),
    ('kitap', 'KITAP (Kartu Izin Tinggal Tetap)', 'immigration', true, 3),
    ('visa_kunjungan', 'Visa Kunjungan (Visit Visa)', 'immigration', true, 4),
    ('voa', 'Visa on Arrival', 'immigration', true, 5),
    ('itas', 'ITAS (Izin Tinggal Terbatas)', 'immigration', true, 6),
    ('itap', 'ITAP (Izin Tinggal Tetap)', 'immigration', true, 7),
    ('rptka', 'RPTKA (Work Permit)', 'immigration', true, 8),
    ('imta', 'IMTA (Work Permit Card)', 'immigration', true, 9),
    ('merp', 'MERP (Exit Re-entry Permit)', 'immigration', true, 10),
    ('sponsor_letter', 'Sponsor Letter', 'immigration', false, 11),
    ('domicile_letter', 'Domicile Letter (SKTT)', 'immigration', true, 12),
    ('stm', 'STM (Surat Tanda Melapor)', 'immigration', true, 13),

    -- PT PMA Documents
    ('nib', 'NIB (Nomor Induk Berusaha)', 'pma', true, 20),
    ('akta_pendirian', 'Akta Pendirian (Deed of Establishment)', 'pma', false, 21),
    ('sk_kemenkumham', 'SK Kemenkumham (Legal Approval)', 'pma', false, 22),
    ('npwp_company', 'NPWP Perusahaan (Company Tax ID)', 'pma', false, 23),
    ('surat_domisili', 'Surat Domisili (Company Domicile)', 'pma', true, 24),
    ('oss_certificate', 'OSS Certificate', 'pma', false, 25),
    ('izin_usaha', 'Izin Usaha (Business License)', 'pma', true, 26),
    ('virtual_office', 'Virtual Office Agreement', 'pma', true, 27),

    -- Tax Documents
    ('npwp', 'NPWP (Personal Tax ID)', 'tax', false, 30),
    ('efin', 'EFIN (Electronic Filing ID)', 'tax', false, 31),
    ('spt_tahunan', 'SPT Tahunan (Annual Tax Return)', 'tax', false, 32),
    ('e_spt', 'e-SPT Filing', 'tax', false, 33),
    ('lkpm', 'LKPM (Investment Report)', 'tax', true, 34),
    ('bpjs_tk', 'BPJS Ketenagakerjaan', 'tax', true, 35),
    ('bpjs_kes', 'BPJS Kesehatan', 'tax', true, 36),
    ('skt', 'SKT (Tax Registration Letter)', 'tax', false, 37),

    -- Personal Documents
    ('photo', 'Photo/Avatar', 'personal', false, 40),
    ('cv', 'CV/Resume', 'personal', false, 41),
    ('diploma', 'Diploma/Certificate', 'personal', false, 42),
    ('marriage_cert', 'Marriage Certificate', 'personal', false, 43),
    ('birth_cert', 'Birth Certificate', 'personal', false, 44),
    ('police_clearance', 'Police Clearance (SKCK)', 'personal', true, 45),
    ('bank_statement', 'Bank Statement', 'personal', false, 46),
    ('health_cert', 'Health Certificate', 'personal', true, 47),

    -- Other
    ('contract', 'Contract/Agreement', 'other', true, 50),
    ('invoice', 'Invoice', 'other', false, 51),
    ('receipt', 'Receipt/Payment Proof', 'other', false, 52),
    ('other', 'Other Document', 'other', false, 99)
ON CONFLICT (code) DO NOTHING;

-- ================================================
-- 5. EXPIRY ALERTS VIEW (with color indicators)
-- ================================================
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
  AND (d.is_archived IS NULL OR d.is_archived = false);

-- ================================================
-- 6. CLIENT PROFILE SUMMARY VIEW
-- ================================================
CREATE OR REPLACE VIEW client_profile_view AS
SELECT
    c.id,
    c.uuid,
    c.full_name,
    c.email,
    c.phone,
    c.whatsapp,
    c.nationality,
    c.passport_number,
    c.passport_expiry,
    c.date_of_birth,
    c.avatar_url,
    c.company_name,
    c.google_drive_folder_id,
    c.status,
    c.client_type,
    c.assigned_to,
    c.notes,
    c.tags,
    c.created_at,
    c.updated_at,
    -- Counts
    (SELECT COUNT(*) FROM client_family_members fm WHERE fm.client_id = c.id) as family_members_count,
    (SELECT COUNT(*) FROM documents d WHERE d.client_id = c.id AND (d.is_archived IS NULL OR d.is_archived = false)) as documents_count,
    (SELECT COUNT(*) FROM practices p WHERE p.client_id = c.id) as practices_count,
    (SELECT COUNT(*) FROM practices p WHERE p.client_id = c.id AND p.status NOT IN ('completed', 'cancelled')) as active_practices_count,
    -- Expiry alerts
    (SELECT COUNT(*) FROM client_expiry_alerts_view e WHERE e.client_id = c.id AND e.alert_color = 'red') as red_alerts_count,
    (SELECT COUNT(*) FROM client_expiry_alerts_view e WHERE e.client_id = c.id AND e.alert_color = 'yellow') as yellow_alerts_count,
    (SELECT COUNT(*) FROM client_expiry_alerts_view e WHERE e.client_id = c.id AND e.alert_color = 'expired') as expired_count
FROM clients c;

-- ================================================
-- COMPLETED: Enhanced Client Profile Schema
-- ================================================
