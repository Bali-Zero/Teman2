-- Migration 034: Company-Centric CRM Architecture
-- Creates companies, client_company_links, and company_documents tables
-- Date: 2026-02-16

-- ============================================
-- TABLE: companies
-- Stores company/PT PMA information
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE DEFAULT gen_random_uuid()::text,
    
    -- Company Basic Info
    company_name VARCHAR(255) NOT NULL,
    company_type VARCHAR(50) NOT NULL DEFAULT 'PT PMA', -- PT PMA, PT Perorangan, CV, etc.
    brand_name VARCHAR(255), -- Optional trade name
    
    -- Business Identification
    kbli_code VARCHAR(20), -- KBLI classification code
    kbli_description TEXT, -- Description of business activity
    nib VARCHAR(50) UNIQUE, -- Nomor Induk Berusaha
    npwp_company VARCHAR(50) UNIQUE, -- Company Tax ID
    
    -- Legal Documents
    akta_pendirian_no VARCHAR(100),
    akta_pendirian_date DATE,
    akta_perubahan_no VARCHAR(100),
    akta_perubahan_date DATE,
    sk_menhumkam_no VARCHAR(100), -- SK Kemenkumham
    sk_menhumkam_date DATE,
    
    -- Address & Contact
    registered_address TEXT,
    office_address TEXT,
    city VARCHAR(100),
    province VARCHAR(100),
    postal_code VARCHAR(20),
    company_phone VARCHAR(50),
    company_email VARCHAR(255),
    
    -- Status & Metadata
    status VARCHAR(50) DEFAULT 'active', -- active, dormant, dissolved, in_setup
    setup_progress INTEGER DEFAULT 0, -- 0-100% setup completion
    
    -- Google Drive Integration
    google_drive_folder_id VARCHAR(100),
    
    -- Custom Fields (JSON for flexibility)
    custom_fields JSONB DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Indexes for companies
CREATE INDEX IF NOT EXISTS idx_companies_uuid ON companies(uuid);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_nib ON companies(nib);
CREATE INDEX IF NOT EXISTS idx_companies_npwp ON companies(npwp_company);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_kbli ON companies(kbli_code);

-- ============================================
-- TABLE: client_company_links
-- Many-to-many relationship between clients and companies
-- ============================================
CREATE TABLE IF NOT EXISTS client_company_links (
    id SERIAL PRIMARY KEY,
    
    -- Relationships
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Role & Association
    role VARCHAR(50) NOT NULL DEFAULT 'shareholder', -- Director, Commissioner, Shareholder, Employee, Agent, Beneficial_Owner
    is_primary BOOLEAN DEFAULT FALSE, -- Is this the primary company for this client?
    
    -- Ownership Details
    ownership_percentage DECIMAL(5,2), -- 0.00 to 100.00
    shares_count INTEGER,
    share_nominal_value DECIMAL(12,2),
    
    -- Dates
    start_date DATE,
    end_date DATE, -- NULL if still active
    
    -- Status
    status VARCHAR(50) DEFAULT 'active', -- active, resigned, terminated, pending
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint: one client can have only one link per company
    UNIQUE(client_id, company_id)
);

-- Indexes for client_company_links
CREATE INDEX IF NOT EXISTS idx_client_company_client ON client_company_links(client_id);
CREATE INDEX IF NOT EXISTS idx_client_company_company ON client_company_links(company_id);
CREATE INDEX IF NOT EXISTS idx_client_company_role ON client_company_links(role);
CREATE INDEX IF NOT EXISTS idx_client_company_status ON client_company_links(status);

-- ============================================
-- TABLE: company_documents
-- Documents specific to companies (akta, SK, NIB, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS company_documents (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE DEFAULT gen_random_uuid()::text,
    
    -- Relationship
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Document Classification
    document_type VARCHAR(100) NOT NULL, -- See list below
    document_subtype VARCHAR(100), -- For finer classification
    
    -- Document Details
    document_number VARCHAR(255),
    document_title VARCHAR(500),
    description TEXT,
    
    -- Dates
    issue_date DATE,
    expiry_date DATE, -- NULL if no expiry
    reminder_date DATE, -- When to remind about expiry
    
    -- File Storage
    storage_type VARCHAR(50) DEFAULT 'google_drive', -- google_drive, local, s3
    google_drive_file_id VARCHAR(255),
    google_drive_file_url TEXT,
    file_name VARCHAR(500),
    file_size_kb INTEGER,
    mime_type VARCHAR(100),
    
    -- Verification
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active', -- active, expired, archived, pending
    
    -- Notes
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by VARCHAR(255)
);

-- Indexes for company_documents
CREATE INDEX IF NOT EXISTS idx_company_docs_company ON company_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_company_docs_type ON company_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_company_docs_status ON company_documents(status);
CREATE INDEX IF NOT EXISTS idx_company_docs_expiry ON company_documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_company_docs_uuid ON company_documents(uuid);

-- ============================================
-- TABLE: tax_records
-- Tax information for both clients and companies
-- ============================================
CREATE TABLE IF NOT EXISTS tax_records (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE DEFAULT gen_random_uuid()::text,
    
    -- Polymorphic relationship (either client or company)
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('client', 'company')),
    entity_id INTEGER NOT NULL,
    
    -- Tax Identification
    npwp VARCHAR(50), -- Nomor Pokok Wajib Pajak
    npwp_status VARCHAR(50), -- active, inactive, pending
    tax_center VARCHAR(100), -- KPP (Tax Office)
    
    -- Tax Types Registration
    is_pph21_registered BOOLEAN DEFAULT FALSE, -- Personal Income Tax
    is_pph23_registered BOOLEAN DEFAULT FALSE, -- Withholding Tax
    is_pph25_registered BOOLEAN DEFAULT FALSE, -- Installment Tax
    is_ppn_registered BOOLEAN DEFAULT FALSE, -- VAT
    is_pph29_registered BOOLEAN DEFAULT FALSE, -- Annual Tax
    
    -- Tax Period
    tax_year INTEGER,
    reporting_period VARCHAR(20), -- monthly, quarterly, annual
    
    -- Obligations & Deadlines
    last_filing_date DATE,
    next_filing_date DATE,
    last_payment_date DATE,
    next_payment_date DATE,
    
    -- Status
    compliance_status VARCHAR(50) DEFAULT 'compliant', -- compliant, overdue, warning, exempt
    
    -- Custom Fields
    custom_fields JSONB DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for tax_records
CREATE INDEX IF NOT EXISTS idx_tax_entity ON tax_records(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_tax_npwp ON tax_records(npwp);
CREATE INDEX IF NOT EXISTS idx_tax_status ON tax_records(compliance_status);
CREATE INDEX IF NOT EXISTS idx_tax_next_filing ON tax_records(next_filing_date);

-- ============================================
-- TABLE: tax_documents
-- Tax-specific documents (SPT, bukti potong, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS tax_documents (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE DEFAULT gen_random_uuid()::text,
    
    -- Relationship
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('client', 'company')),
    entity_id INTEGER NOT NULL,
    
    -- Document Classification
    document_type VARCHAR(100) NOT NULL, -- SPT, Bukti_Potong, SSP, etc.
    tax_type VARCHAR(50), -- PPh21, PPh23, PPN, etc.
    tax_year INTEGER,
    tax_period VARCHAR(20), -- Jan, Feb, Q1, etc.
    
    -- Document Details
    document_number VARCHAR(255),
    filing_date DATE,
    
    -- Amounts
    reported_amount DECIMAL(15,2),
    paid_amount DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'IDR',
    
    -- File Storage
    storage_type VARCHAR(50) DEFAULT 'google_drive',
    google_drive_file_id VARCHAR(255),
    google_drive_file_url TEXT,
    file_name VARCHAR(500),
    
    -- Status
    status VARCHAR(50) DEFAULT 'filed', -- filed, paid, corrected, amended
    
    -- Notes
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by VARCHAR(255)
);

-- Indexes for tax_documents
CREATE INDEX IF NOT EXISTS idx_tax_docs_entity ON tax_documents(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_tax_docs_type ON tax_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_tax_docs_tax_type ON tax_documents(tax_type);
CREATE INDEX IF NOT EXISTS idx_tax_docs_year ON tax_documents(tax_year);

-- ============================================
-- TRIGGER: Update timestamps automatically
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_client_company_links_updated_at ON client_company_links;
CREATE TRIGGER update_client_company_links_updated_at
    BEFORE UPDATE ON client_company_links
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_company_documents_updated_at ON company_documents;
CREATE TRIGGER update_company_documents_updated_at
    BEFORE UPDATE ON company_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tax_records_updated_at ON tax_records;
CREATE TRIGGER update_tax_records_updated_at
    BEFORE UPDATE ON tax_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS: For easier querying
-- ============================================

-- View: Companies with primary contact
CREATE OR REPLACE VIEW companies_with_contact AS
SELECT 
    c.*,
    cl.client_id as primary_contact_id,
    cl.role as primary_contact_role,
    cl.ownership_percentage
FROM companies c
LEFT JOIN client_company_links cl ON c.id = cl.company_id AND cl.is_primary = TRUE;

-- View: Client company associations
CREATE OR REPLACE VIEW client_companies_view AS
SELECT 
    cl.*,
    c.full_name as client_name,
    c.email as client_email,
    c.phone as client_phone,
    comp.company_name,
    comp.company_type,
    comp.nib,
    comp.status as company_status
FROM client_company_links cl
JOIN clients c ON cl.client_id = c.id
JOIN companies comp ON cl.company_id = comp.id;

-- ============================================
-- DOCUMENT TYPE ENUMS (for reference)
-- ============================================
-- company_documents.document_type:
--   akta_pendirian, akta_perubahan, sk_menhumkam,
--   nib, npwp, skt, sppkp, tdp, 
--   domicile_letter, decrees, licenses, contracts, others
--
-- tax_documents.document_type:
--   SPT, Bukti_Potong, SSP, Faktur_Pajak, 
--   SKT, SPPKP, Tax_Certificate, Others
--
-- client_company_links.role:
--   Director, Commissioner, Shareholder, Employee, 
--   Agent, Beneficial_Owner, Authorized_Signatory

-- Mark migration as complete
-- INSERT INTO schema_migrations (version, applied_at) VALUES (34, NOW());
