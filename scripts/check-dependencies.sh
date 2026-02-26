#!/bin/bash
# Script to check for outdated dependencies

set -e

echo "🔍 Checking dependencies..."

# Python dependencies
if [ -f "apps/backend-rag/requirements.txt" ]; then
    echo ""
    echo "📦 Python Dependencies (backend-rag):"
    cd apps/backend-rag
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        pip list --outdated 2>/dev/null | head -20 || echo "Could not check outdated packages"
    else
        echo "⚠️  Virtual environment not found. Run: python3 -m venv .venv"
    fi
    cd ../..
fi

# Node.js dependencies
if [ -f "package.json" ]; then
    echo ""
    echo "📦 Node.js Dependencies:"
    npm outdated 2>/dev/null | head -20 || echo "Could not check outdated packages"
fi

# Security audits
echo ""
echo "🔒 Security Audits:"
if command -v npm &> /dev/null; then
    echo "Running npm audit..."
    npm audit --audit-level=moderate 2>/dev/null || echo "npm audit completed"
fi

if command -v pip-audit &> /dev/null; then
    echo "Running pip-audit..."
    pip-audit 2>/dev/null || echo "pip-audit not available"
elif [ -f "apps/backend-rag/requirements.txt" ]; then
    echo "⚠️  pip-audit not installed. Install with: pip install pip-audit"
fi

echo ""
echo "✅ Dependency check complete"
