#!/bin/bash
#
# Brevo (SendGrid) API Key Setup
# ==============================
# Usage: ./setup_brevo.sh <brevo_api_key>

set -e

API_KEY="${1:-}"
APP_NAME="${2:-backend-rag}"

if [ -z "$API_KEY" ]; then
    echo "❌ Error: Brevo API key required"
    echo "Usage: $0 <brevo_api_key>"
    exit 1
fi

echo "🔧 Configuring Brevo for $APP_NAME..."
echo ""

# Set secrets
echo "📦 Setting secrets on Fly.io..."
flyctl secrets set SENDGRID_API_KEY="$API_KEY" -a "$APP_NAME"
flyctl secrets set EMAIL_PROVIDER=sendgrid -a "$APP_NAME"

echo ""
echo "🚀 Restarting app to apply changes..."
flyctl restart -a "$APP_NAME"

echo ""
echo "✅ Brevo configured successfully!"
echo ""
echo "API Key: ${API_KEY:0:20}...${API_KEY: -8}"
echo ""
echo "Test the configuration:"
echo "  python scripts/verify_sendgrid.py your-email@example.com"
echo ""
echo "Send test email:"
echo "  curl -X POST https://backend-rag.fly.dev/api/notifications/test/ \\"
echo "    -H \"Authorization: Bearer TOKEN\" \\"
echo "    -d '{\"force_send\": true, \"test_email\": \"you@example.com\"}'"
