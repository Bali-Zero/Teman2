#!/bin/bash
# Script per analizzare e decidere cosa tracciare nel git

echo "📋 Analisi File Non Tracciati"
echo "=============================="
echo ""

# Categorie di file
echo "📁 DOCUMENTAZIONE:"
git status --porcelain | grep "^??" | grep -E "\.md$|README|DOCUMENTATION" | head -10
echo ""

echo "🔧 SCRIPT/UTILITY:"
git status --porcelain | grep "^??" | grep -E "scripts/|\.py$|\.sh$" | head -10
echo ""

echo "💻 CODICE SOURCE:"
git status --porcelain | grep "^??" | grep -E "src/|\.ts$|\.tsx$" | head -10
echo ""

echo "📊 REPORT:"
git status --porcelain | grep "^??" | grep -E "REPORT|SUMMARY|COMPLETION" | head -10
echo ""

echo "🧪 TEST:"
git status --porcelain | grep "^??" | grep -E "test|spec" | head -10
echo ""

echo "📝 RACCOMANDAZIONI:"
echo "✅ DA TRACCIARE:"
echo "  - Documentazione (.md in docs/)"
echo "  - Script utili (scripts/*.py, scripts/*.sh)"
echo "  - Codice source nuovo (src/, hooks/, components/)"
echo "  - Report di fix completati"
echo ""
echo "❌ DA IGNORARE:"
echo "  - File temporanei di test (test_github_token.py)"
echo "  - File di sessione temporanei"
echo "  - Directory vuote o non necessarie"
