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
    linked_client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    portal_access BOOLEAN NOT NULL DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    company_type VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS client_company_links (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'active',
    end_date TIMESTAMPTZ
);

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
    file_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    client_visible BOOLEAN DEFAULT TRUE,
    expiry_date TIMESTAMPTZ,
    file_url TEXT,
    file_id TEXT,
    file_size_kb INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_visible BOOLEAN NOT NULL DEFAULT TRUE
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
