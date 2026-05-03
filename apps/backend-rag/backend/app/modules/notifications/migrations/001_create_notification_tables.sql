-- ============================================================================
-- Notification System Database Schema
-- ============================================================================
-- Created: 2024-02-17
-- Description: Tables for automated email notification system
-- Following @ai_onboarding philosophy: clear, documented, indexed
-- ============================================================================

-- Table: notification_alerts
-- Stores all generated alerts and their sending status
CREATE TABLE IF NOT EXISTS notification_alerts (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    message TEXT,
    email_subject VARCHAR(500),
    email_body TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    
    -- Constraints
    CONSTRAINT valid_alert_type CHECK (alert_type IN (
        'passport_warning',
        'passport_critical', 
        'passport_expired',
        'visa_warning',
        'visa_critical',
        'visa_expired',
        'birthday'
    )),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'sent', 'failed', 'suppressed'))
);

-- Index: Prevent duplicate alerts per day per client per type
CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_alerts_unique_daily 
ON notification_alerts (client_id, alert_type, DATE(created_at));

-- Index: Find pending alerts efficiently
CREATE INDEX IF NOT EXISTS idx_notification_alerts_pending 
ON notification_alerts (status, created_at) 
WHERE status = 'pending';

-- Index: Find alerts by client
CREATE INDEX IF NOT EXISTS idx_notification_alerts_client 
ON notification_alerts (client_id, created_at DESC);

-- Index: Find alerts by type and date (for deduplication)
CREATE INDEX IF NOT EXISTS idx_notification_alerts_type_date 
ON notification_alerts (client_id, alert_type, sent_at DESC);

-- ============================================================================
-- Table: notification_settings
-- Per-client notification preferences
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_settings (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT true,
    passport_alerts_enabled BOOLEAN DEFAULT true,
    visa_alerts_enabled BOOLEAN DEFAULT true,
    birthday_greetings_enabled BOOLEAN DEFAULT true,
    preferred_language VARCHAR(5) DEFAULT 'en',
    min_alert_days INTEGER DEFAULT 1, -- Minimum days between same alert type
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_client_settings UNIQUE (client_id)
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_notification_settings_client 
ON notification_settings (client_id);

-- ============================================================================
-- Table: notification_log
-- Audit log of all notification activities
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER REFERENCES notification_alerts(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL, -- 'generated', 'sent', 'failed', 'suppressed'
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_notification_log_client 
ON notification_log (client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_log_action 
ON notification_log (action, created_at DESC);

-- ============================================================================
-- Function: Update updated_at timestamp
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for notification_settings
DROP TRIGGER IF EXISTS update_notification_settings_updated_at ON notification_settings;
CREATE TRIGGER update_notification_settings_updated_at
    BEFORE UPDATE ON notification_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Initial data: Create default settings for all existing clients
-- ============================================================================
INSERT INTO notification_settings (client_id, preferred_language)
SELECT id, COALESCE(preferred_language, 'en')
FROM clients
WHERE is_active = true
ON CONFLICT (client_id) DO NOTHING;

-- ============================================================================
-- Comments for documentation
-- ============================================================================
COMMENT ON TABLE notification_alerts IS 'Stores all generated alerts for passport, visa, and birthday notifications';
COMMENT ON TABLE notification_settings IS 'Per-client notification preferences and settings';
COMMENT ON TABLE notification_log IS 'Audit log of all notification activities for compliance';
