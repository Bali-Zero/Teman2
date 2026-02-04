#!/bin/bash

# Add Sentry environment variables to Vercel
# This script adds all 5 required Sentry variables for Production, Preview, and Development

set -e

cd "$(dirname "$0")"

echo "🔧 Adding Sentry environment variables to Vercel..."
echo ""

DSN="https://17c537c4e5404cad63eba6f614b7f27c@o4510530384101376.ingest.us.sentry.io/4510530418311168"
ORG="bali-zero-7p"
PROJECT="mouth"
TOKEN="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"

echo "1/5 Adding NEXT_PUBLIC_SENTRY_DSN..."
echo "$DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN production --force 2>&1 | grep -v "Vercel CLI" || true
echo "$DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN preview --force 2>&1 | grep -v "Vercel CLI" || true
echo "$DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN development --force 2>&1 | grep -v "Vercel CLI" || true

echo "2/5 Adding SENTRY_DSN..."
echo "$DSN" | vercel env add SENTRY_DSN production --force 2>&1 | grep -v "Vercel CLI" || true
echo "$DSN" | vercel env add SENTRY_DSN preview --force 2>&1 | grep -v "Vercel CLI" || true
echo "$DSN" | vercel env add SENTRY_DSN development --force 2>&1 | grep -v "Vercel CLI" || true

echo "3/5 Adding SENTRY_ORG..."
echo "$ORG" | vercel env add SENTRY_ORG production --force 2>&1 | grep -v "Vercel CLI" || true
echo "$ORG" | vercel env add SENTRY_ORG preview --force 2>&1 | grep -v "Vercel CLI" || true
echo "$ORG" | vercel env add SENTRY_ORG development --force 2>&1 | grep -v "Vercel CLI" || true

echo "4/5 Adding SENTRY_PROJECT..."
echo "$PROJECT" | vercel env add SENTRY_PROJECT production --force 2>&1 | grep -v "Vercel CLI" || true
echo "$PROJECT" | vercel env add SENTRY_PROJECT preview --force 2>&1 | grep -v "Vercel CLI" || true
echo "$PROJECT" | vercel env add SENTRY_PROJECT development --force 2>&1 | grep -v "Vercel CLI" || true

echo "5/5 Adding SENTRY_AUTH_TOKEN..."
echo "$TOKEN" | vercel env add SENTRY_AUTH_TOKEN production --force 2>&1 | grep -v "Vercel CLI" || true
echo "$TOKEN" | vercel env add SENTRY_AUTH_TOKEN preview --force 2>&1 | grep -v "Vercel CLI" || true
echo "$TOKEN" | vercel env add SENTRY_AUTH_TOKEN development --force 2>&1 | grep -v "Vercel CLI" || true

echo ""
echo "✅ All Sentry environment variables added to Vercel!"
echo ""
echo "Verify:"
vercel env ls | grep SENTRY
echo ""
echo "Next step: Deploy"
echo "  git push origin main"
echo "  or: vercel --prod"
