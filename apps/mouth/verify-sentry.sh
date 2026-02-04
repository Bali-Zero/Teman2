#!/bin/bash

# Sentry Configuration Verification Script
# This script verifies that Sentry is correctly configured in apps/mouth/

set -e

echo "🔍 Verifying Sentry Configuration for apps/mouth/"
echo "================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Not in apps/mouth directory"
    echo "   Please run: cd apps/mouth && ./verify-sentry.sh"
    exit 1
fi

# Check if Sentry package is installed
echo "1️⃣ Checking @sentry/nextjs package..."
if grep -q "@sentry/nextjs" package.json; then
    SENTRY_VERSION=$(grep "@sentry/nextjs" package.json | sed 's/.*: "//;s/".*//')
    echo "   ✅ @sentry/nextjs installed (version: $SENTRY_VERSION)"
else
    echo "   ❌ @sentry/nextjs not found in package.json"
    exit 1
fi
echo ""

# Check Sentry configuration files
echo "2️⃣ Checking Sentry configuration files..."
REQUIRED_FILES=(
    "sentry.client.config.ts"
    "sentry.server.config.ts"
    "sentry.edge.config.ts"
    "src/instrumentation.ts"
    "src/app/global-error.tsx"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file missing"
        exit 1
    fi
done
echo ""

# Check .env.example for Sentry variables
echo "3️⃣ Checking .env.example for Sentry variables..."
REQUIRED_ENV_VARS=(
    "NEXT_PUBLIC_SENTRY_DSN"
    "SENTRY_DSN"
    "SENTRY_ORG"
    "SENTRY_PROJECT"
    "SENTRY_AUTH_TOKEN"
)

for var in "${REQUIRED_ENV_VARS[@]}"; do
    if grep -q "$var" .env.example; then
        echo "   ✅ $var"
    else
        echo "   ❌ $var missing from .env.example"
        exit 1
    fi
done
echo ""

# Check next.config.ts for Sentry integration
echo "4️⃣ Checking next.config.ts for Sentry integration..."
if grep -q "withSentryConfig" next.config.ts; then
    echo "   ✅ withSentryConfig found"
else
    echo "   ❌ withSentryConfig not found in next.config.ts"
    exit 1
fi

if grep -q "sentryWebpackPluginOptions" next.config.ts; then
    echo "   ✅ sentryWebpackPluginOptions found"
else
    echo "   ❌ sentryWebpackPluginOptions not found in next.config.ts"
    exit 1
fi
echo ""

# Check TypeScript compilation
echo "5️⃣ Running TypeScript type check..."
if pnpm typecheck > /dev/null 2>&1; then
    echo "   ✅ TypeScript compilation successful"
else
    echo "   ❌ TypeScript compilation failed"
    echo "   Run 'pnpm typecheck' to see errors"
    exit 1
fi
echo ""

# Check if .env.local exists (optional but recommended)
echo "6️⃣ Checking for .env.local (optional but recommended)..."
if [ -f ".env.local" ]; then
    if grep -q "SENTRY_DSN" .env.local 2>/dev/null; then
        echo "   ✅ .env.local exists with Sentry config"
        echo "   ⚠️  Make sure it's not committed to git!"
    else
        echo "   ⚠️  .env.local exists but no Sentry config found"
        echo "   Add Sentry credentials to enable error tracking"
    fi
else
    echo "   ⚠️  .env.local not found"
    echo "   Create it from .env.example and add your Sentry credentials"
fi
echo ""

# Summary
echo "================================================"
echo "✅ Sentry Configuration Verification Complete!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. If you haven't already, create a Sentry project:"
echo "   → https://sentry.io/organizations/[your-org]/projects/new/"
echo ""
echo "2. Get your credentials:"
echo "   → DSN: Settings → Projects → mouth → Client Keys (DSN)"
echo "   → Org: Settings → General Settings → Organization Slug"
echo "   → Auth Token: Settings → Developer Settings → Auth Tokens"
echo ""
echo "3. Create .env.local with your credentials:"
echo "   cp .env.example .env.local"
echo "   # Then add your Sentry values"
echo ""
echo "4. Test local build:"
echo "   pnpm build"
echo ""
echo "5. Add secrets to Fly.io:"
echo "   flyctl secrets set NEXT_PUBLIC_SENTRY_DSN=\"...\" \\"
echo "     SENTRY_DSN=\"...\" \\"
echo "     SENTRY_ORG=\"...\" \\"
echo "     SENTRY_PROJECT=\"mouth\" \\"
echo "     SENTRY_AUTH_TOKEN=\"...\""
echo ""
echo "6. Deploy to production:"
echo "   flyctl deploy"
echo ""
echo "📚 Documentation:"
echo "   • Quick guide: SENTRY_SETUP.md"
echo "   • Full docs: ../../docs/SENTRY_CONFIGURATION.md"
echo "   • Examples: ../../docs/SENTRY_USAGE_EXAMPLES.md"
echo ""
