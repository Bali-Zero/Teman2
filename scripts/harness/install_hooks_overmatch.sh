#!/usr/bin/env bash
# install_hooks_overmatch.sh — applica i fix dei 3 bug guard-over-match agli hook live.
# OPERATOR-RUN: hooks/ è blindato dal carve-out host-boundary by-design. Lancia:
#   bash scripts/harness/install_hooks_overmatch.sh
# Idempotente, backup-first (.bak-overmatch). Ri-testa dopo l'applicazione.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "═══ applico i fix agli hook live (~/.claude/hooks) ═══"
python3 "$HERE/fix_hooks_overmatch.py"

echo ""
echo "═══ ri-test post-applicazione ═══"
python3 "$HERE/test_hooks_overmatch.py"

echo ""
echo "✓ FATTO. Backup: ~/.claude/hooks/{worktree_isolation,guardrails-static}.py.bak-overmatch"
echo "  Effettivo: i nuovi hook girano dalla PROSSIMA sessione (gli hook si rileggono all'avvio)."
echo "  Per provarli SUBITO in questa sessione: chiedi a Claude di ri-testare un 'npm install' e un 'python -c'."
