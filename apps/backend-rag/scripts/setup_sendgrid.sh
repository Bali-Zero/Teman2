#!/bin/bash
#
# SendGrid Setup Script for Fly.io
# ================================
# This script configures SendGrid for the notification system.
#
# Prerequisites:
# 1. SendGrid account (https://sendgrid.com)
# 2. API Key created in SendGrid Dashboard
# 3. Domain authenticated in SendGrid (recommended)
# 4. flyctl installed and authenticated
#
# Usage:
#   ./setup_sendgrid.sh <sendgrid_api_key>
#
# Example:
#   ./setup_sendgrid.sh SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

set -e

API_KEY="${1:-}"
APP_NAME="${2:-backend-rag}"

if [ -z "$API_KEY" ]; then
    echo "❌ Error: SendGrid API key required"
    echo "Usage: $0 <sendgrid_api_key> [app_name]"
    echo ""
    echo "Get your API key from: https://app.sendgrid.com/settings/api_keys"
    exit 1
fi

echo "🔧 Setting up SendGrid for $APP_NAME..."
echo ""

# Set secrets
echo "📦 Setting secrets..."
flyctl secrets set SENDGRID_API_KEY="$API_KEY" -a "$APP_NAME"
flyctl secrets set EMAIL_PROVIDER=sendgrid -a "$APP_NAME"

echo ""
echo "✅ SendGrid configured successfully!"
echo ""
echo "Next steps:"
echo "1. Verify sender authentication in SendGrid: https://app.sendgrid.com/settings/sender_auth"
echo "2. Test email sending with the test endpoint:"
echo "   POST /api/notifications/test/"
echo "   {"
echo "     \"client_id\": 123,"
echo "     \"alert_type\": \"birthday\","
echo "     \"force_send\": true,"
echo "     \"test_email\": \"your-email@example.com\""
echo "   }"
echo ""
echo "3. Monitor email activity in SendGrid: https://app.sendgrid.com/email_activity"
