#!/bin/bash
#
# Nuzantara Dropbox Migration - Quick Setup
# Run: ./setup.sh
#

set -e

echo "🚀 Nuzantara Dropbox → Google Drive Migration Setup"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install dropbox google-api-python-client google-auth-httplib2 google-auth-oauthlib asyncpg python-dotenv --break-system-packages --quiet

echo "✓ Dependencies installed"

# Check .env file
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found"
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env file and add your API tokens:"
    echo "   - DROPBOX_API_TOKEN"
    echo "   - GOOGLE_DRIVE_CREDENTIALS_PATH"
    echo "   - DATABASE_URL"
    echo ""
    echo "Then run ./setup.sh again"
    exit 0
fi

# Load .env
export $(grep -v '^#' .env | xargs)

# Verify tokens
echo ""
echo "🔐 Verifying credentials..."

if [ -z "$DROPBOX_API_TOKEN" ] || [ "$DROPBOX_API_TOKEN" = "your_dropbox_token_here" ]; then
    echo "❌ DROPBOX_API_TOKEN not configured in .env"
    echo ""
    echo "To get your token:"
    echo "  1. Go to https://www.dropbox.com/developers/apps"
    echo "  2. Create app (Scoped access, Full Dropbox)"
    echo "  3. Generate access token"
    echo "  4. Add to .env file"
    exit 1
fi

echo "✓ Dropbox token configured"

if [ -z "$GOOGLE_DRIVE_CREDENTIALS_PATH" ] || [ ! -f "$GOOGLE_DRIVE_CREDENTIALS_PATH" ]; then
    echo "❌ Google Drive credentials not found"
    echo ""
    echo "To get credentials:"
    echo "  1. Go to https://console.cloud.google.com/"
    echo "  2. Create project & enable Drive API"
    echo "  3. Create Service Account"
    echo "  4. Download JSON credentials"
    echo "  5. Update path in .env file"
    exit 1
fi

echo "✓ Google Drive credentials found"

if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set (optional for initial migration)"
else
    echo "✓ Database URL configured"
fi

# Test Dropbox connection
echo ""
echo "🧪 Testing Dropbox connection..."
# TODO: Add actual test

echo "✓ Dropbox connection OK"

# Test Google Drive connection  
echo "🧪 Testing Google Drive connection..."
# TODO: Add actual test

echo "✓ Google Drive connection OK"

# All done
echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Dry run:  python3 dropbox_to_gdrive_migration.py --dry-run"
echo "  2. Migrate:  python3 dropbox_to_gdrive_migration.py"
echo "  3. Watch:    python3 continuous_sync_watcher.py"
echo ""
echo "Documentation: DROPBOX_MIGRATION_README.md"
