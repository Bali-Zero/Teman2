#!/bin/bash
# ZANTARA MEDIA - Deployment Script
# Deploys the application to Fly.io

set -e

echo "============================================"
echo "ZANTARA MEDIA - Deployment"
echo "============================================"
echo ""

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "❌ Fly.io CLI not found. Install it first:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in
if ! fly auth whoami &> /dev/null; then
    echo "❌ Not logged in to Fly.io"
    echo "   Run: fly auth login"
    exit 1
fi

echo "✓ Fly.io CLI ready"
echo ""

# Ask for confirmation
read -p "Deploy zantara-media to Fly.io? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "Deploying..."
echo ""

# Deploy
fly deploy

echo ""
echo "============================================"
echo "Deployment completed!"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Check status:"
echo "   fly status"
echo ""
echo "2. View logs:"
echo "   fly logs"
echo ""
echo "3. Test the API:"
echo "   curl https://zantara-media.fly.dev/health"
echo ""
echo "4. Trigger pipeline:"
echo "   curl -X POST https://zantara-media.fly.dev/api/automation/trigger"
echo ""
echo "5. Check scheduler:"
echo "   curl https://zantara-media.fly.dev/api/automation/status"
echo ""
