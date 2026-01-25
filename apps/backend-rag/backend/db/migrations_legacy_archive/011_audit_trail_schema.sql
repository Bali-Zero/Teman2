-- ================================================
-- Migration 011: Audit Trail System
-- Purpose: Create tables for authentication and system audit logs
-- Created: 2025-11-30
-- ================================================

BEGIN;

-- ========================================
-- AUTH AUDIT LOG TABLE
-- ========================================
-- Tracks all authentication attempts (success/failure)

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255), -- Nullable because failed logins might not match a user
    email VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL, -- 'login', 'logout', 'failed_login', 'refresh', 'revoke'
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT false,
    failure_reason TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for fast lookup/analysis
CREATE INDEX IF NOT EXISTS idx_auth_audit_email ON auth_audit_log(email);
CREATE INDEX IF NOT EXISTS idx_auth_audit_timestamp ON auth_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_auth_audit_ip ON auth_audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_auth_audit_action ON auth_audit_log(action);

-- ========================================
-- SYSTEM AUDIT EVENTS TABLE
-- ========================================
-- General purpose audit trail for system actions (GDPR, compliance)

CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL, -- 'data_access', 'configuration_change', 'security_alert'
    user_id VARCHAR(255), -- Who performed the action
    resource_id VARCHAR(255), -- What was accessed/modified
    action VARCHAR(50) NOT NULL, -- 'read', 'write', 'delete', 'update'
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp DESC);

-- Comments
COMMENT ON TABLE auth_audit_log IS 'Security log for all authentication attempts';
COMMENT ON TABLE audit_events IS 'General system audit trail for compliance and security';

COMMIT;
