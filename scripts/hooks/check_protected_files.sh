#!/usr/bin/env bash
# Anti-rogue-AI gate: block commits that modify OFF-LIMITS files
# These files must NEVER be modified by AI agents without explicit human review.
# History: modifying dependencies.py broke all 89 routers in production (feb-2026).
#
# Declared override (owner ruling 2026-10-12): zantara_core.py — and ONLY that
# file — may be committed when ZANTARA_CORE_EDIT carries a real reason. Before
# this, the only escape was `--no-verify`, which also skipped every other hook
# (secret guards included) and which agents are forbidden to use, so an
# owner-authorized edit had no path at all. The override is the local mirror of
# the CI gate (.github/workflows/zantara-core-edit-gate.yml), which still
# requires `Zantara-Core-Edit: <reason>` in the PR body. fly.toml and
# alembic/env.py have no override.
set -euo pipefail

PROTECTED=$(git diff --cached --name-only 2>/dev/null | \
    grep -E "(zantara_core\.py|fly\.toml|alembic/env\.py)" || true)

if [ -z "$PROTECTED" ]; then
    echo "✅ No OFF-LIMITS files modified"
    exit 0
fi

REASON="${ZANTARA_CORE_EDIT:-}"
# Strip surrounding whitespace before judging the reason.
REASON="$(printf '%s' "$REASON" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

# A reason counts only if it is substantive and not the placeholder copied
# from this message ("<reason>" or anything starting with "<").
REASON_OK=0
if [ "${#REASON}" -ge 10 ] && [ "${REASON#<}" = "$REASON" ]; then
    REASON_OK=1
fi

NON_CORE=$(printf '%s\n' "$PROTECTED" | grep -vE "zantara_core\.py$" || true)

if [ "$REASON_OK" -eq 1 ] && [ -z "$NON_CORE" ]; then
    echo "⚠️  OFF-LIMITS override: zantara_core.py committed with declared reason:"
    echo "   ZANTARA_CORE_EDIT=$REASON"
    echo "   The PR body must carry the matching 'Zantara-Core-Edit:' line (CI gate)."
    exit 0
fi

echo ""
echo "❌ BLOCKED: modifica a file OFF-LIMITS rilevata:"
echo "$PROTECTED"
echo ""
echo "   Questi file NON devono essere modificati da AI agent senza review esplicita."
if [ -n "$NON_CORE" ]; then
    echo "   fly.toml / alembic/env.py non hanno override: rimuovili dal commit"
    echo "   (git restore --staged <file>) e falli committare a un umano."
else
    echo "   Solo per zantara_core.py, con autorizzazione esplicita dell'owner:"
    echo "   ZANTARA_CORE_EDIT='motivo reale (>=10 caratteri)' git commit ..."
    echo "   e nel body della PR la riga 'Zantara-Core-Edit: <motivo>'."
fi
exit 1
