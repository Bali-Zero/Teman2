#!/usr/bin/env bash
# Anti-rogue-AI gate: block commits that modify OFF-LIMITS files
# These files must NEVER be modified by AI agents without explicit human review.
# History: modifying dependencies.py broke all 89 routers in production (feb-2026).
set -euo pipefail

PROTECTED=$(git diff --cached --name-only 2>/dev/null | \
    grep -E "(zantara_core\.py|fly\.toml|alembic/env\.py)" || true)

if [ -n "$PROTECTED" ]; then
    echo ""
    echo "❌ BLOCKED: modifica a file OFF-LIMITS rilevata:"
    echo "$PROTECTED"
    echo ""
    echo "   Questi file NON devono essere modificati da AI agent senza review esplicita."
    echo "   Se la modifica è intenzionale:"
    echo "   1. Rimuovi dal commit: git restore --staged <file>"
    echo "   2. Fai review manuale"
    echo "   3. Committa con: git commit --no-verify -m 'intentional: <motivo>'"
    exit 1
fi

echo "✅ No OFF-LIMITS files modified"
