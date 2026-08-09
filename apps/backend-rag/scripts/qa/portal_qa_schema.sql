-- Disposable, synthetic-only schema for the my.balizero.com prod-like gate.
-- Apply only to a loopback PostgreSQL database whose name starts with
-- `my_portal_qa`. This intentionally contains no production data.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    whatsapp VARCHAR(50),
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    passport_expiry DATE,
    visa_expiry DATE,
    date_of_birth DATE,
    gender VARCHAR(50),
    address TEXT,
    assigned_to VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS client_family_members (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    date_of_birth DATE,
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    passport_expiry DATE,
    current_visa_type VARCHAR(100),
    visa_expiry DATE,
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_alerts (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'failed', 'suppressed')),
    message TEXT,
    email_subject VARCHAR(500),
    email_body TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    created_date DATE GENERATED ALWAYS AS
        ((created_at AT TIME ZONE 'UTC')::DATE) STORED
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_alert_daily
    ON notification_alerts (client_id, alert_type, created_date);

CREATE TABLE IF NOT EXISTS team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    name VARCHAR(255),
    pin_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    avatar TEXT,
    avatar_url TEXT,
    linked_client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    portal_access BOOLEAN NOT NULL DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE team_members ADD COLUMN IF NOT EXISTS avatar_url TEXT;

CREATE TABLE IF NOT EXISTS notification_prefs (
    user_id UUID PRIMARY KEY,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    wa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    wa_phone VARCHAR(20),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS practice_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS practices (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_type_id INTEGER REFERENCES practice_types(id),
    practice_type_code VARCHAR(100),
    status VARCHAR(100) NOT NULL DEFAULT 'inquiry',
    missing_documents JSONB,
    client_visible BOOLEAN DEFAULT TRUE,
    start_date TIMESTAMPTZ,
    completion_date TIMESTAMPTZ,
    expiry_date TIMESTAMPTZ,
    payment_status VARCHAR(50) DEFAULT 'pending',
    quoted_price NUMERIC(18, 2),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE practices ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE practices ADD COLUMN IF NOT EXISTS quoted_price NUMERIC(18, 2);
ALTER TABLE practices ADD COLUMN IF NOT EXISTS service_type TEXT;

-- Synthetic Partner self-service slice. Actor columns use the UUID identity
-- type of this disposable harness; production uses VARCHAR team-member IDs.
-- The self-view rows keep those actor fields NULL, while all Partner entity
-- and commission shapes mirror migration 119 exactly.
CREATE TABLE IF NOT EXISTS partners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    work_role TEXT,
    company_name TEXT,
    office_address TEXT,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    preferred_language TEXT DEFAULT 'id',
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('individual', 'corporate_pt', 'corporate_cv', 'foreign')),
    npwp TEXT,
    nik TEXT,
    tax_withholding_category TEXT NOT NULL DEFAULT 'tbd'
        CHECK (tax_withholding_category IN ('pph21', 'pph23', 'exempt', 'tbd')),
    fiscal_address TEXT,
    bank_name TEXT,
    bank_account_holder TEXT,
    bank_account_number TEXT,
    ewallet_type TEXT,
    ewallet_number TEXT,
    payment_currency TEXT NOT NULL DEFAULT 'IDR',
    iban TEXT,
    payment_notes TEXT,
    default_commission_type TEXT NOT NULL DEFAULT 'percentage'
        CHECK (default_commission_type IN ('percentage', 'flat')),
    default_commission_value NUMERIC(14, 4) NOT NULL DEFAULT 10.0,
    onboarding_status TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (onboarding_status IN ('pending_approval', 'active', 'inactive')),
    assigned_to UUID REFERENCES team_members(id) ON DELETE SET NULL,
    pdp_consent_at TIMESTAMPTZ,
    pdp_consent_version TEXT,
    terms_accepted_at TIMESTAMPTZ,
    terms_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES team_members(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,
    welcome_email_sent_at TIMESTAMPTZ
);

ALTER TABLE team_members
    ADD COLUMN IF NOT EXISTS partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS partner_referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE RESTRICT,
    share_percent NUMERIC(5, 2) NOT NULL DEFAULT 100.00
        CHECK (share_percent > 0 AND share_percent <= 100),
    referred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    referred_by_user_id UUID REFERENCES team_members(id) ON DELETE SET NULL,
    notes TEXT,
    CONSTRAINT partner_referrals_practice_unique_v1 UNIQUE (practice_id)
);

CREATE TABLE IF NOT EXISTS partner_commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    referral_id UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
    practice_id INTEGER REFERENCES practices(id) ON DELETE RESTRICT,
    entry_type TEXT NOT NULL
        CHECK (entry_type IN ('accrual', 'clawback', 'manual_adjustment')),
    related_commission_id UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
    base_amount_idr NUMERIC(16, 2) NOT NULL,
    commission_type_snapshot TEXT NOT NULL
        CHECK (commission_type_snapshot IN ('percentage', 'flat')),
    commission_value_snapshot NUMERIC(14, 4) NOT NULL,
    rule_source TEXT NOT NULL DEFAULT 'partner_default'
        CHECK (rule_source IN ('partner_default', 'manual_override')),
    assigned_to_snapshot UUID REFERENCES team_members(id) ON DELETE SET NULL,
    gross_amount_idr NUMERIC(16, 2) NOT NULL,
    withholding_category TEXT NOT NULL DEFAULT 'tbd'
        CHECK (withholding_category IN ('pph21', 'pph23', 'exempt', 'tbd')),
    withholding_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.0,
    withholding_amount_idr NUMERIC(16, 2) NOT NULL DEFAULT 0.0,
    net_amount_idr NUMERIC(16, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'accrued'
        CHECK (status IN (
            'accrued', 'approved', 'paid', 'clawback_pending',
            'offset_applied', 'waived', 'repaid'
        )),
    accrued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eligible_for_approval_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES team_members(id) ON DELETE SET NULL,
    paid_at TIMESTAMPTZ,
    paid_by UUID REFERENCES team_members(id) ON DELETE SET NULL,
    paid_via TEXT,
    payment_reference TEXT,
    payment_proof_url TEXT,
    receipt_type TEXT
        CHECK (receipt_type IS NULL OR receipt_type IN ('kwitansi', 'invoice', 'none')),
    receipt_file_url TEXT,
    manual_override_reason TEXT,
    clawback_reason TEXT,
    waiver_reason TEXT,
    idempotency_key TEXT UNIQUE,
    commission_email_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    invoice_number VARCHAR(100) NOT NULL,
    amount_idr NUMERIC(18, 2) NOT NULL DEFAULT 0,
    invoice_source VARCHAR(50),
    drive_file_id TEXT,
    drive_web_link TEXT,
    email_sent_to_client BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    company_type VARCHAR(100),
    nib VARCHAR(100),
    npwp_company VARCHAR(100),
    kbli_code VARCHAR(100),
    status VARCHAR(50),
    registered_address TEXT,
    company_email VARCHAR(255),
    company_phone VARCHAR(50),
    akta_pendirian_no VARCHAR(255),
    akta_pendirian_date DATE,
    sk_menhumkam_no VARCHAR(255),
    custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS client_company_links (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    ownership_percentage NUMERIC(5, 2),
    status VARCHAR(50) DEFAULT 'active',
    end_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_workspace_ai_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL,
    client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('notebooklm', 'gemini', 'manual')),
    notebook_id TEXT,
    note_id TEXT,
    source_file_ids TEXT[] NOT NULL DEFAULT '{}',
    facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
    created_by TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        status <> 'approved'
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_company_status
    ON crm_workspace_ai_snapshots (company_id, status, approved_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_client_status
    ON crm_workspace_ai_snapshots (client_id, status, approved_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_facts
    ON crm_workspace_ai_snapshots USING GIN (facts);

CREATE TABLE IF NOT EXISTS portal_messages (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    subject VARCHAR(255),
    direction VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sent_by VARCHAR(255) NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    document_type VARCHAR(100),
    document_category VARCHAR(100),
    file_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    uploaded_by VARCHAR(255),
    uploaded_source VARCHAR(50),
    client_visible BOOLEAN DEFAULT TRUE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    expiry_date TIMESTAMPTZ,
    file_url TEXT,
    file_id TEXT,
    file_size_kb INTEGER,
    mime_type VARCHAR(255),
    document_purpose TEXT,
    storage_type VARCHAR(50),
    storage_path TEXT,
    extracted_text TEXT,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(255),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    token_hash CHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_ip VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cross-funnel analytics exercised by authenticated portal pages. Keep this
-- disposable contract aligned with migration_109_funnel_sessions.py so a
-- successful data recovery cannot be misclassified as an outage when its
-- fire-and-forget analytics event is persisted.
DO $$ BEGIN
    CREATE TYPE funnel_type_enum AS ENUM (
        'visa', 'kbli', 'tax', 'property', 'home'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS funnel_sessions (
    session_id              VARCHAR(64) PRIMARY KEY,
    funnel                  funnel_type_enum NOT NULL,
    step_state              JSONB DEFAULT '{}'::jsonb,
    lead_profile            JSONB DEFAULT '{}'::jsonb,
    first_touched_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_touched_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    converted_to_client_id  UUID NULL,
    ip_hash                 VARCHAR(64),
    expires_at              TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

CREATE INDEX IF NOT EXISTS idx_funnel_sessions_funnel_last_touched
    ON funnel_sessions (funnel, last_touched_at DESC);
CREATE INDEX IF NOT EXISTS idx_funnel_sessions_converted
    ON funnel_sessions (converted_to_client_id)
    WHERE converted_to_client_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_funnel_sessions_expires_at
    ON funnel_sessions (expires_at);

CREATE TABLE IF NOT EXISTS funnel_attributions (
    id                      BIGSERIAL PRIMARY KEY,
    client_id               UUID NOT NULL,
    session_id              VARCHAR(64) NOT NULL,
    first_funnel            funnel_type_enum NOT NULL,
    touchpoints             JSONB DEFAULT '[]'::jsonb,
    first_touch_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    converted_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_funnel_attributions_client
    ON funnel_attributions (client_id);

CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_visible BOOLEAN NOT NULL DEFAULT TRUE,
    color VARCHAR(50) DEFAULT 'info',
    CONSTRAINT chk_timeline_event_type CHECK (
        event_type IN (
            'deadline', 'milestone', 'document_request', 'document_received',
            'status_change', 'payment_due', 'appointment', 'reminder', 'completion'
        )
    ),
    CONSTRAINT chk_timeline_color CHECK (
        color IN ('info', 'warning', 'success', 'error')
    )
);

CREATE TABLE IF NOT EXISTS practice_required_documents (
    id SERIAL PRIMARY KEY,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL,
    document_label VARCHAR(255) NOT NULL,
    description TEXT,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_by_client BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    client_notes TEXT,
    team_member_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portal_notifications (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_preferences (
    id SERIAL PRIMARY KEY,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email_notifications BOOLEAN DEFAULT FALSE,
    whatsapp_notifications BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'Asia/Makassar',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT,
    email VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    failure_reason TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Mirrors migration_090_security_audit_log.py. The auth revoke-all route writes
-- this best-effort audit row independently from the Redis revocation effect.
CREATE TABLE IF NOT EXISTS security_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_audit_user
    ON security_audit_log(user_email, created_at);
CREATE INDEX IF NOT EXISTS idx_security_audit_action
    ON security_audit_log(action, created_at);
CREATE INDEX IF NOT EXISTS idx_security_audit_created
    ON security_audit_log(created_at);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id TEXT,
    resource_id TEXT,
    action VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Client-safe LKPM slice used by the prod-like portal gate. These columns
-- mirror the legacy 063 + company cascade + receipt 108 contracts without
-- carrying any production records or credentials.
CREATE TABLE IF NOT EXISTS lkpm_client_config (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    company_id INTEGER,
    company_name TEXT NOT NULL,
    npwp TEXT,
    nib TEXT,
    kbli_codes TEXT[] NOT NULL DEFAULT '{}',
    planned_equipment_domestic BIGINT NOT NULL DEFAULT 0,
    planned_equipment_import BIGINT NOT NULL DEFAULT 0,
    planned_building_domestic BIGINT NOT NULL DEFAULT 0,
    planned_building_import BIGINT NOT NULL DEFAULT 0,
    planned_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
    planned_vehicle_import BIGINT NOT NULL DEFAULT 0,
    planned_land BIGINT NOT NULL DEFAULT 0,
    planned_working_capital BIGINT NOT NULL DEFAULT 0,
    planned_other BIGINT NOT NULL DEFAULT 0,
    planned_tki INTEGER NOT NULL DEFAULT 0,
    planned_tka INTEGER NOT NULL DEFAULT 0,
    jurnal_api_key TEXT,
    jurnal_company_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lkpm_client UNIQUE (client_id, company_id)
);

CREATE TABLE IF NOT EXISTS lkpm_reports (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    company_id INTEGER,
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    lkpm_assigned_to TEXT,
    realized_equipment_domestic BIGINT DEFAULT 0,
    realized_equipment_import BIGINT DEFAULT 0,
    realized_building_domestic BIGINT DEFAULT 0,
    realized_building_import BIGINT DEFAULT 0,
    realized_vehicle_domestic BIGINT DEFAULT 0,
    realized_vehicle_import BIGINT DEFAULT 0,
    realized_land BIGINT DEFAULT 0,
    realized_working_capital BIGINT DEFAULT 0,
    realized_other BIGINT DEFAULT 0,
    cumulative_equipment_domestic BIGINT DEFAULT 0,
    cumulative_equipment_import BIGINT DEFAULT 0,
    cumulative_building_domestic BIGINT DEFAULT 0,
    cumulative_building_import BIGINT DEFAULT 0,
    cumulative_vehicle_domestic BIGINT DEFAULT 0,
    cumulative_vehicle_import BIGINT DEFAULT 0,
    cumulative_land BIGINT DEFAULT 0,
    cumulative_working_capital BIGINT DEFAULT 0,
    cumulative_other BIGINT DEFAULT 0,
    current_tki INTEGER NOT NULL DEFAULT 0,
    current_tka INTEGER NOT NULL DEFAULT 0,
    quarterly_revenue BIGINT NOT NULL DEFAULT 0,
    annual_revenue BIGINT NOT NULL DEFAULT 0,
    narrative_obstacles TEXT,
    narrative_plans TEXT,
    validation_status TEXT NOT NULL DEFAULT 'pending',
    validation_alerts JSONB NOT NULL DEFAULT '[]',
    validated_at TIMESTAMPTZ,
    validated_by TEXT,
    client_approved BOOLEAN NOT NULL DEFAULT FALSE,
    client_approved_at TIMESTAMPTZ,
    oss_submitted BOOLEAN NOT NULL DEFAULT FALSE,
    oss_submitted_at TIMESTAMPTZ,
    oss_submitted_by TEXT,
    oss_receipt_number TEXT,
    oss_receipt_file_url TEXT,
    data_source TEXT NOT NULL DEFAULT 'manual',
    has_ai_categorized_items BOOLEAN NOT NULL DEFAULT FALSE,
    ai_categorized_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lkpm_report UNIQUE (client_id, company_id, quarter, year)
);

CREATE INDEX IF NOT EXISTS idx_lkpm_reports_company
    ON lkpm_reports (company_id);

CREATE TABLE IF NOT EXISTS lkpm_receipts (
    id SERIAL PRIMARY KEY,
    lkpm_report_id INTEGER NOT NULL
        REFERENCES lkpm_reports(id) ON DELETE CASCADE,
    nomor_laporan TEXT NOT NULL,
    nomor_kegiatan_usaha TEXT NOT NULL,
    kbli_code VARCHAR(10),
    kegiatan_usaha_desc TEXT,
    stage TEXT,
    oss_status TEXT,
    lokasi TEXT,
    tanggal_diterima DATE,
    nama_perusahaan_oss TEXT,
    file_drive_id TEXT,
    file_drive_url TEXT,
    file_name TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,
    CONSTRAINT uq_lkpm_receipts_nomor_laporan UNIQUE (nomor_laporan)
);

CREATE INDEX IF NOT EXISTS idx_lkpm_receipts_report
    ON lkpm_receipts (lkpm_report_id);
