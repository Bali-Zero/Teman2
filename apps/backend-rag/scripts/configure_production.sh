#!/bin/bash
#
# Production Configuration Script for Notifications
# ==================================================
# Complete setup guide for the notification system.
#
# This script will:
# 1. Check prerequisites
# 2. Configure SendGrid (if API key provided)
# 3. Run database migrations
# 4. Verify configuration
#
# Usage:
#   ./configure_production.sh [SENDGRID_API_KEY]
#
# If SENDGRID_API_KEY is not provided, it will only run migrations.

set -e

APP_NAME="${APP_NAME:-backend-rag}"
DB_APP_NAME="${DB_APP_NAME:-nuzantara-db}"
SENDGRID_API_KEY="${1:-}"

echo "═══════════════════════════════════════════════════════════════"
echo "  Bali Zero Notification System - Production Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl not found"
    echo "   Install from: https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Check if logged in to Fly.io
if ! flyctl auth whoami &> /dev/null; then
    echo "❌ Not logged in to Fly.io"
    echo "   Run: flyctl auth login"
    exit 1
fi

echo "✅ Fly.io CLI configured"
echo ""

# Step 1: SendGrid Configuration
if [ -n "$SENDGRID_API_KEY" ]; then
    echo "Step 1: Configuring SendGrid..."
    echo "─────────────────────────────────────────────────────────────"
    
    flyctl secrets set SENDGRID_API_KEY="$SENDGRID_API_KEY" -a "$APP_NAME"
    flyctl secrets set EMAIL_PROVIDER=sendgrid -a "$APP_NAME"
    
    echo "✅ SendGrid configured"
    echo ""
else
    echo "⚠️  Step 1: Skipping SendGrid configuration (no API key provided)"
    echo "   To configure later, run:"
    echo "   flyctl secrets set SENDGRID_API_KEY=xxx -a $APP_NAME"
    echo ""
fi

# Step 2: Database Migration
echo "Step 2: Running database migrations..."
echo "─────────────────────────────────────────────────────────────"

# Create migration SQL file
MIGRATION_SQL=$(cat << 'EOF'
-- ============================================================================
-- Notification System Database Schema
-- ============================================================================

-- Table: notification_alerts
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

-- Unique index to prevent duplicate alerts per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_alerts_unique_daily 
ON notification_alerts (client_id, alert_type, DATE(created_at));

-- Index for pending alerts
CREATE INDEX IF NOT EXISTS idx_notification_alerts_pending 
ON notification_alerts (status, created_at) 
WHERE status = 'pending';

-- Index for client lookups
CREATE INDEX IF NOT EXISTS idx_notification_alerts_client 
ON notification_alerts (client_id, created_at DESC);

-- Table: notification_settings
CREATE TABLE IF NOT EXISTS notification_settings (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT true,
    passport_alerts_enabled BOOLEAN DEFAULT true,
    visa_alerts_enabled BOOLEAN DEFAULT true,
    birthday_greetings_enabled BOOLEAN DEFAULT true,
    preferred_language VARCHAR(5) DEFAULT 'en',
    min_alert_days INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_client_settings UNIQUE (client_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_settings_client 
ON notification_settings (client_id);

-- Table: notification_log
CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER REFERENCES notification_alerts(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_log_client 
ON notification_log (client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_log_action 
ON notification_log (action, created_at DESC);

-- Initialize default settings for existing clients
INSERT INTO notification_settings (client_id, preferred_language)
SELECT id, COALESCE(preferred_language, 'en')
FROM clients
WHERE is_active = true
ON CONFLICT (client_id) DO NOTHING;

-- Add columns to clients table if not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'clients' AND column_name = 'preferred_language') THEN
        ALTER TABLE clients ADD COLUMN preferred_language VARCHAR(5) DEFAULT 'en';
    END IF;
END $$;

COMMENT ON TABLE notification_alerts IS 'Stores all generated alerts for passport, visa, and birthday notifications';
COMMENT ON TABLE notification_settings IS 'Per-client notification preferences and settings';
COMMENT ON TABLE notification_log IS 'Audit log of all notification activities for compliance';
EOF
)

# Save to temp file
TEMP_FILE=$(mktemp)
echo "$MIGRATION_SQL" > "$TEMP_FILE"

echo "📄 Migration file created"
echo "🚀 Running migration on $DB_APP_NAME..."

# Execute migration using flyctl postgres connect
if flyctl postgres connect -a "$DB_APP_NAME" < "$TEMP_FILE"; then
    echo "✅ Database migration completed"
else
    echo "❌ Database migration failed"
    echo "   You can run it manually:"
    echo "   flyctl postgres connect -a $DB_APP_NAME"
    echo "   Then paste the SQL from: backend/app/modules/notifications/migrations/001_create_notification_tables.sql"
fi

# Cleanup
rm "$TEMP_FILE"
echo ""

# Step 3: Verify Configuration
echo "Step 3: Verifying configuration..."
echo "─────────────────────────────────────────────────────────────"

# Check if backend is running
if flyctl status -a "$APP_NAME" | grep -q "running"; then
    echo "✅ Backend app is running"
else
    echo "⚠️  Backend app may not be running"
    echo "   Check status: flyctl status -a $APP_NAME"
fi

# Check environment variables
echo ""
echo "📋 Current environment variables:"
flyctl secrets list -a "$APP_NAME" | grep -E "(SENDGRID|EMAIL)" || echo "   No email secrets configured yet"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ -n "$SENDGRID_API_KEY" ]; then
    echo "✅ SendGrid configured"
    echo "✅ Database migrated"
    echo ""
    echo "Next steps:"
    echo "1. Test email sending:"
    echo "   curl -X POST https://backend-rag.fly.dev/api/notifications/test/ \\"
    echo "     -H \"Authorization: Bearer YOUR_TOKEN\" \\"
    echo "     -d '{\"force_send\": true, \"test_email\": \"your@email.com\"}'"
    echo ""
    echo "2. Access admin dashboard:"
    echo "   https://kita.balizero.com/notifications"
    echo ""
    echo "3. Monitor SendGrid activity:"
    echo "   https://app.sendgrid.com/email_activity"
else
    echo "✅ Database migrated"
    echo "⚠️  SendGrid not configured"
    echo ""
    echo "To complete setup, get a SendGrid API key from:"
    echo "https://app.sendgrid.com/settings/api_keys"
    echo ""
    echo "Then run:"
    echo "  flyctl secrets set SENDGRID_API_KEY=xxx -a $APP_NAME"
    echo "  flyctl secrets set EMAIL_PROVIDER=sendgrid -a $APP_NAME"
fi

echo ""
echo "For troubleshooting, check logs:"
echo "  flyctl logs -a $APP_NAME"
echo ""
