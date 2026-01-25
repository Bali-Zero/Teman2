-- Oracle Knowledge Bases Migration
-- Created: 2025-10-21
-- Purpose: Migrate static JSON knowledge bases from Oracle System to PostgreSQL

-- ========================================
-- VISA TYPES TABLE
-- ========================================
-- Replaces visa-oracle-kb.json visaTypes section

CREATE TABLE IF NOT EXISTS visa_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- e.g. OFFICIAL_VISA_CODE, KITAS_INVESTOR, etc
    name VARCHAR(255) NOT NULL,
    duration VARCHAR(100),
    extensions VARCHAR(100),
    total_stay VARCHAR(100),
    renewable BOOLEAN DEFAULT false,

    -- Processing
    processing_time_normal VARCHAR(100),
    processing_time_express VARCHAR(100),
    processing_timeline JSONB, -- Complex timelines (RPTKA, Visa, KITAS steps)

    -- Costs
    cost_visa VARCHAR(100),
    cost_extension VARCHAR(100),
    cost_details JSONB, -- Detailed cost breakdown

    -- Requirements & Restrictions
    requirements TEXT[], -- Array of requirements
    restrictions TEXT[], -- Array of restrictions
    allowed_activities TEXT[],
    benefits TEXT[],
    process_steps TEXT[],
    tips TEXT[],

    -- Classification
    category VARCHAR(50), -- tourism, business, investor, working, permanent
    foreign_eligible BOOLEAN DEFAULT true,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visa_types_code ON visa_types(code);
CREATE INDEX IF NOT EXISTS idx_visa_types_category ON visa_types(category);

-- ========================================
-- IMMIGRATION OFFICES TABLE
-- ========================================
-- Replaces visa-oracle-kb.json immigrationOffices section

CREATE TABLE IF NOT EXISTS immigration_offices (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- DENPASAR, SINGARAJA, etc
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    province VARCHAR(100) DEFAULT 'Bali',

    -- Hours & Timing
    hours VARCHAR(255),
    best_time VARCHAR(255),
    avoid_time VARCHAR(255),

    -- Practical Info
    parking TEXT,
    tips TEXT[],
    less_crowded BOOLEAN DEFAULT false,
    services TEXT[],

    -- Location
    lat FLOAT,
    lng FLOAT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_immigration_offices_city ON immigration_offices(city);

-- ========================================
-- COMMON ISSUES TABLE
-- ========================================
-- Replaces visa-oracle-kb.json commonIssues section

CREATE TABLE IF NOT EXISTS immigration_issues (
    id SERIAL PRIMARY KEY,
    issue_type VARCHAR(50) NOT NULL, -- rejection, delay, overstay, lost_passport
    reason_or_cause TEXT NOT NULL,
    solution TEXT NOT NULL,
    frequency_pct FLOAT, -- Percentage or null
    impact_days INTEGER, -- Delay in days or null
    prevention TEXT,

    -- Steps for complex solutions
    steps TEXT[],
    timeline VARCHAR(100),

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_immigration_issues_type ON immigration_issues(issue_type);

-- ========================================
-- BUSINESS STRUCTURES TABLE (KBLI)
-- ========================================
-- Replaces kbli-eye-kb.json businessStructures section

CREATE TABLE IF NOT EXISTS business_structures (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- PT_PMA, LOCAL_PT, CV, YAYASAN
    name VARCHAR(255) NOT NULL,
    name_indonesian VARCHAR(255),

    -- Capital & Investment
    minimum_capital VARCHAR(100),
    minimum_investment VARCHAR(100),
    ownership_rules TEXT,

    -- Requirements
    requirements TEXT[],

    -- Timeline & Costs
    timeline_details JSONB, -- Detailed breakdown (deed, approval, NIB, etc)
    timeline_total VARCHAR(100),
    costs JSONB, -- notary, licenses, capital requirements

    -- Advantages & Restrictions
    advantages TEXT[],
    restrictions TEXT[],

    -- Structure
    structure_info TEXT, -- For CV, YAYASAN special structures
    purpose TEXT, -- For YAYASAN

    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_structures_code ON business_structures(code);

-- ========================================
-- KBLI CODES TABLE
-- ========================================
-- Replaces kbli-eye-kb.json kbliDatabase.popularKBLI section

CREATE TABLE IF NOT EXISTS kbli_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL, -- 70209, 62019, 55104, etc
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category_letter VARCHAR(5), -- A-S categories
    category_name VARCHAR(255), -- "Professional Services", etc

    -- Eligibility
    foreign_eligible BOOLEAN DEFAULT false,
    minimum_investment VARCHAR(100),

    -- Licensing
    licenses TEXT[], -- ["NIB", "TDUP", "Health Permit"]

    -- Popularity & Usage
    popularity VARCHAR(20), -- VERY_HIGH, HIGH, MEDIUM, LOW

    -- Guidance
    tips TEXT,
    restrictions TEXT,
    alternative_code VARCHAR(10), -- For closed sectors

    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kbli_codes_code ON kbli_codes(code);
CREATE INDEX IF NOT EXISTS idx_kbli_codes_category ON kbli_codes(category_letter);
CREATE INDEX IF NOT EXISTS idx_kbli_codes_foreign_eligible ON kbli_codes(foreign_eligible);
CREATE INDEX IF NOT EXISTS idx_kbli_codes_popularity ON kbli_codes(popularity);

-- ========================================
-- KBLI COMBINATIONS TABLE
-- ========================================
-- Replaces kbli-eye-kb.json kbliDatabase.combinations section

CREATE TABLE IF NOT EXISTS kbli_combinations (
    id SERIAL PRIMARY KEY,
    package_name VARCHAR(100) UNIQUE NOT NULL, -- digitalNomadPackage, hospitalityPackage
    display_name VARCHAR(255),
    kbli_codes TEXT[], -- Array of KBLI codes
    description TEXT,
    use_case TEXT,

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- LICENSES TABLE
-- ========================================
-- Replaces kbli-eye-kb.json licenses section

CREATE TABLE IF NOT EXISTS indonesian_licenses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- NIB, SIUP, TDP, TDUP, etc
    full_name VARCHAR(255) NOT NULL,
    purpose TEXT,
    validity VARCHAR(100),
    process_info TEXT,

    -- Requirements
    requirements TEXT[],
    required_for TEXT, -- "For all businesses", specific sectors

    -- Restrictions
    restrictions TEXT[],

    -- Status
    status VARCHAR(50), -- "active", "integrated_in_nib", "deprecated"
    integrated_into VARCHAR(50), -- If deprecated, which license replaced it

    -- Sectors (for specific licenses like TDUP)
    applicable_sectors TEXT[],

    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_licenses_code ON indonesian_licenses(code);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON indonesian_licenses(status);

-- ========================================
-- OSS SYSTEM INFO TABLE
-- ========================================
-- Replaces kbli-eye-kb.json ossSystem section

CREATE TABLE IF NOT EXISTS oss_system_info (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL, -- "url", "status", "maintenance_schedule"
    value TEXT,
    value_array TEXT[], -- For features, tips arrays

    metadata JSONB DEFAULT '{}'::jsonb,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- OSS COMMON ISSUES TABLE
-- ========================================
-- Replaces kbli-eye-kb.json ossSystem.commonIssues

CREATE TABLE IF NOT EXISTS oss_issues (
    id SERIAL PRIMARY KEY,
    issue_category VARCHAR(50), -- "systemErrors", "processIssues"
    error_or_issue TEXT NOT NULL,
    solution TEXT NOT NULL,
    frequency_description VARCHAR(100),
    timeline VARCHAR(100),
    browser_recommendation VARCHAR(50),

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oss_issues_category ON oss_issues(issue_category);

-- ========================================
-- COMPLIANCE CALENDAR TABLE
-- ========================================
-- Replaces kbli-eye-kb.json complianceCalendar section

CREATE TABLE IF NOT EXISTS compliance_deadlines (
    id SERIAL PRIMARY KEY,
    deadline_type VARCHAR(50) NOT NULL, -- "monthly", "quarterly", "annual"
    deadline_day VARCHAR(50), -- "10th", "15th", "endOfMonth", "march", etc
    task_name VARCHAR(255) NOT NULL,
    applies_to TEXT, -- "All PMA companies", etc
    platform VARCHAR(100),
    penalty TEXT,

    -- For recurring
    recurring BOOLEAN DEFAULT true,

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_deadlines_type ON compliance_deadlines(deadline_type);

-- ========================================
-- RECENT UPDATES TABLE
-- ========================================
-- Replaces visa-oracle-kb.json recentUpdates section
-- This is more dynamic - could also be scraped intel

CREATE TABLE IF NOT EXISTS regulatory_updates (
    id SERIAL PRIMARY KEY,
    update_date DATE NOT NULL,
    source VARCHAR(100) NOT NULL, -- "visa_oracle", "kbli_eye", "oss", etc
    update_title TEXT NOT NULL,
    update_description TEXT NOT NULL,
    impact TEXT,

    -- Classification
    update_type VARCHAR(50), -- regulation, fee_change, system_change, new_visa
    impact_level VARCHAR(20), -- critical, high, medium, low

    url TEXT,

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regulatory_updates_date ON regulatory_updates(update_date DESC);
CREATE INDEX IF NOT EXISTS idx_regulatory_updates_source ON regulatory_updates(source);
CREATE INDEX IF NOT EXISTS idx_regulatory_updates_impact ON regulatory_updates(impact_level);

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE visa_types IS 'Visa types and requirements from VISA ORACLE knowledge base';
COMMENT ON TABLE immigration_offices IS 'Immigration office locations and practical information';
COMMENT ON TABLE immigration_issues IS 'Common visa/immigration issues and solutions';
COMMENT ON TABLE business_structures IS 'Business entity types (PT PMA, Local PT, CV, etc)';
COMMENT ON TABLE kbli_codes IS 'Indonesian business classification codes (KBLI)';
COMMENT ON TABLE kbli_combinations IS 'Pre-configured KBLI packages for common business types';
COMMENT ON TABLE indonesian_licenses IS 'Business licenses and permits information';
COMMENT ON TABLE oss_system_info IS 'OSS system metadata and configuration';
COMMENT ON TABLE oss_issues IS 'Common OSS system issues and solutions';
COMMENT ON TABLE compliance_deadlines IS 'Recurring compliance deadlines calendar';
COMMENT ON TABLE regulatory_updates IS 'Recent regulatory changes and announcements';

-- ========================================
-- END OF MIGRATION
-- ========================================
