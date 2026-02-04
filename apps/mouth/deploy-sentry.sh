#!/bin/bash

# Sentry Production Deployment - Interactive Guide
# This script will guide you through deploying Sentry to Vercel

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║           🚀 Sentry Production Deployment - Interactive Guide               ║"
echo "║                                                                              ║"
echo "║                          apps/mouth/ → Vercel                                ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Not in apps/mouth directory"
    echo "   Please run: cd apps/mouth && ./deploy-sentry.sh"
    exit 1
fi

echo "📋 This script will help you:"
echo "   1. Create Sentry project"
echo "   2. Get credentials"
echo "   3. Add to .env.local (optional)"
echo "   4. Add to Vercel environment variables"
echo "   5. Deploy to production"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
fi

echo ""
echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 1: Create Sentry Project                                               │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "1. Open your browser and go to: https://sentry.io"
echo "2. Login or create an account"
echo "3. Click 'Create Project'"
echo "4. Select platform: Next.js"
echo "5. Project name: mouth"
echo "6. Click 'Create Project'"
echo ""

read -p "Press ENTER when you've created the project..."
echo ""

echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 2: Get DSN (Data Source Name)                                          │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "After creating the project, you should see the DSN on the screen."
echo "It looks like: https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxx@o123456.ingest.sentry.io/123456"
echo ""
echo "Or get it from: Settings → Projects → mouth → Client Keys (DSN)"
echo ""

read -p "Enter your SENTRY_DSN: " SENTRY_DSN
echo ""

if [ -z "$SENTRY_DSN" ]; then
    echo "❌ Error: DSN cannot be empty"
    exit 1
fi

echo "✅ DSN saved"
echo ""

echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 3: Get Organization Slug                                               │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Get from: Settings → General Settings → Organization Slug"
echo ""

read -p "Enter your SENTRY_ORG (e.g., my-company): " SENTRY_ORG
echo ""

if [ -z "$SENTRY_ORG" ]; then
    echo "❌ Error: Organization slug cannot be empty"
    exit 1
fi

echo "✅ Organization slug saved"
echo ""

echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 4: Create Auth Token (for Source Maps)                                 │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "1. Go to: Settings → Developer Settings → Auth Tokens"
echo "2. Click 'Create New Token'"
echo "3. Name: mouth-source-maps"
echo "4. Permissions:"
echo "   ✅ Project: Read & Write"
echo "   ✅ Release: Admin"
echo "5. Click 'Create Token'"
echo "6. ⚠️  IMPORTANT: Copy the token immediately (won't be shown again)"
echo ""

read -p "Enter your SENTRY_AUTH_TOKEN: " SENTRY_AUTH_TOKEN
echo ""

if [ -z "$SENTRY_AUTH_TOKEN" ]; then
    echo "❌ Error: Auth token cannot be empty"
    exit 1
fi

echo "✅ Auth token saved"
echo ""

echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 5: Add to .env.local (Optional but Recommended)                        │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""

read -p "Do you want to add credentials to .env.local for local testing? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Adding to .env.local..."
    
    # Backup existing .env.local
    if [ -f ".env.local" ]; then
        cp .env.local .env.local.backup
        echo "✅ Backed up existing .env.local to .env.local.backup"
    fi
    
    # Append Sentry config
    cat >> .env.local <<EOF

# Sentry Configuration (Added $(date +%Y-%m-%d))
NEXT_PUBLIC_SENTRY_DSN=$SENTRY_DSN
SENTRY_DSN=$SENTRY_DSN
SENTRY_ORG=$SENTRY_ORG
SENTRY_PROJECT=mouth
SENTRY_AUTH_TOKEN=$SENTRY_AUTH_TOKEN
EOF
    
    echo "✅ Added Sentry credentials to .env.local"
    echo ""
    
    # Test build
    read -p "Do you want to test the build locally? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Running test build..."
        pnpm build
        echo ""
        echo "✅ Build successful! Source maps should be uploaded."
    fi
fi

echo ""
echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 6: Add to Vercel Environment Variables                                 │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Choose deployment method:"
echo ""
echo "  [1] Vercel Dashboard (Recommended - visual interface)"
echo "  [2] Vercel CLI (Faster - command line)"
echo ""

read -p "Choose option (1 or 2): " -n 1 -r
echo

if [[ $REPLY == "1" ]]; then
    echo ""
    echo "📋 Manual Steps via Vercel Dashboard:"
    echo ""
    echo "1. Go to: https://vercel.com/dashboard"
    echo "2. Select project: mouth"
    echo "3. Go to: Settings → Environment Variables"
    echo "4. Add these 5 variables for Production, Preview, and Development:"
    echo ""
    echo "   Variable Name: NEXT_PUBLIC_SENTRY_DSN"
    echo "   Value: $SENTRY_DSN"
    echo ""
    echo "   Variable Name: SENTRY_DSN"
    echo "   Value: $SENTRY_DSN"
    echo ""
    echo "   Variable Name: SENTRY_ORG"
    echo "   Value: $SENTRY_ORG"
    echo ""
    echo "   Variable Name: SENTRY_PROJECT"
    echo "   Value: mouth"
    echo ""
    echo "   Variable Name: SENTRY_AUTH_TOKEN"
    echo "   Value: $SENTRY_AUTH_TOKEN"
    echo ""
    
    read -p "Press ENTER when you've added all variables..."
    echo ""
    echo "✅ Variables should now be configured on Vercel"
    
elif [[ $REPLY == "2" ]]; then
    echo ""
    echo "Adding variables via Vercel CLI..."
    echo ""
    
    # Check if vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        echo "⚠️  Vercel CLI not found"
        echo "   Install: npm i -g vercel"
        exit 1
    fi
    
    # Add variables
    echo "Adding NEXT_PUBLIC_SENTRY_DSN..."
    echo "$SENTRY_DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN production
    echo "$SENTRY_DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN preview
    echo "$SENTRY_DSN" | vercel env add NEXT_PUBLIC_SENTRY_DSN development
    
    echo "Adding SENTRY_DSN..."
    echo "$SENTRY_DSN" | vercel env add SENTRY_DSN production
    echo "$SENTRY_DSN" | vercel env add SENTRY_DSN preview
    echo "$SENTRY_DSN" | vercel env add SENTRY_DSN development
    
    echo "Adding SENTRY_ORG..."
    echo "$SENTRY_ORG" | vercel env add SENTRY_ORG production
    echo "$SENTRY_ORG" | vercel env add SENTRY_ORG preview
    echo "$SENTRY_ORG" | vercel env add SENTRY_ORG development
    
    echo "Adding SENTRY_PROJECT..."
    echo "mouth" | vercel env add SENTRY_PROJECT production
    echo "mouth" | vercel env add SENTRY_PROJECT preview
    echo "mouth" | vercel env add SENTRY_PROJECT development
    
    echo "Adding SENTRY_AUTH_TOKEN..."
    echo "$SENTRY_AUTH_TOKEN" | vercel env add SENTRY_AUTH_TOKEN production
    echo "$SENTRY_AUTH_TOKEN" | vercel env add SENTRY_AUTH_TOKEN preview
    echo "$SENTRY_AUTH_TOKEN" | vercel env add SENTRY_AUTH_TOKEN development
    
    echo ""
    echo "✅ All variables added to Vercel"
fi

echo ""
echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 7: Deploy to Production                                                │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Choose deployment method:"
echo ""
echo "  [1] Auto-deploy (git push - recommended)"
echo "  [2] Manual deploy (vercel --prod)"
echo ""

read -p "Choose option (1 or 2): " -n 1 -r
echo

if [[ $REPLY == "1" ]]; then
    echo ""
    echo "📋 To trigger auto-deploy:"
    echo ""
    echo "  git add ."
    echo "  git commit -m \"feat: add Sentry error tracking\""
    echo "  git push origin main"
    echo ""
    echo "Vercel will auto-deploy when you push to main branch."
    echo ""
    
    read -p "Do you want to commit and push now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        git commit -m "feat: add Sentry error tracking"
        git push origin main
        echo ""
        echo "✅ Pushed to main. Vercel will deploy automatically."
    fi
    
elif [[ $REPLY == "2" ]]; then
    echo ""
    echo "Deploying via Vercel CLI..."
    
    # Check if vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        echo "⚠️  Vercel CLI not found"
        echo "   Install: npm i -g vercel"
        exit 1
    fi
    
    vercel --prod
    
    echo ""
    echo "✅ Deployment complete"
fi

echo ""
echo "┌──────────────────────────────────────────────────────────────────────────────┐"
echo "│ STEP 8: Verify Deployment                                                   │"
echo "└──────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "1. Check deployment: https://vercel.com/dashboard"
echo "2. Wait for deployment to complete (~2-3 min)"
echo "3. Visit: https://balizero.com"
echo "4. Open DevTools Console and run:"
echo "   throw new Error('[TEST] Sentry tracking');"
echo "5. Check Sentry dashboard (within 5-10 seconds):"
echo "   https://sentry.io/organizations/$SENTRY_ORG/issues/"
echo ""
echo "You should see:"
echo "   ✅ Error appears in Sentry"
echo "   ✅ Stack trace with original file names (source maps working)"
echo "   ✅ Browser info, URL, user context"
echo ""

read -p "Press ENTER to open Sentry dashboard..."
open "https://sentry.io/organizations/$SENTRY_ORG/issues/" 2>/dev/null || echo "Visit: https://sentry.io/organizations/$SENTRY_ORG/issues/"

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║                     ✅ Sentry Deployment Complete!                           ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Summary:"
echo "   ✅ Sentry project created: mouth"
echo "   ✅ Credentials configured"
echo "   ✅ Environment variables added to Vercel"
echo "   ✅ Deployment triggered"
echo ""
echo "📚 Documentation:"
echo "   • Quick guide: SENTRY_SETUP.md"
echo "   • Full docs: ../../docs/SENTRY_CONFIGURATION.md"
echo "   • Deployment guide: SENTRY_PRODUCTION_DEPLOYMENT.md"
echo ""
echo "🔗 Links:"
echo "   • Sentry Dashboard: https://sentry.io/organizations/$SENTRY_ORG/issues/"
echo "   • Vercel Dashboard: https://vercel.com/dashboard"
echo "   • Production Site: https://balizero.com"
echo ""
echo "🎉 Happy monitoring!"
echo ""
