#!/usr/bin/env bash
# launchd_cicatrix_lint.sh — Cicatrix sentinel for sibling-agent plist resurrection
#
# Per cicatrix-scars.md 2026-05-13/19 (WR2 canva-renderer purge panel):
# Preserving plist under ~/Library/LaunchAgents/ IS the attack surface for
# sibling-agent resurrection. Correct posture: physical move to .disabled-YYYY-MM-DD/
# directory + script archival under scripts/.disabled-YYYY-MM-DD/.
#
# This hook fails the push if any plist matching the PURGED_LABELS list is
# detected in the active LaunchAgents dir (i.e. someone tried to resurrect it).
#
# Exit codes:
#   0 = no resurrection detected, push allowed
#   1 = resurrection detected, push BLOCKED
#   2 = lint script error (LaunchAgents dir missing, etc.)

set -euo pipefail

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# Labels that have been formally purged per cicatrix decisions.
# Format: one label per line, no .plist extension.
# Add new entries when a launchd label is purged via .disabled-YYYY-MM-DD/ move.
PURGED_LABELS=(
    "com.balizero.wr2.canva-renderer"  # purged 2026-05-19 (panel cicatrix WR2)
)

if [[ ! -d "$LAUNCH_AGENTS_DIR" ]]; then
    echo "⚠️  launchd_cicatrix_lint: $LAUNCH_AGENTS_DIR not found — skipping"
    exit 0
fi

RESURRECTED=()
for label in "${PURGED_LABELS[@]}"; do
    # Match exact <label>.plist (not in .disabled-*/ subdir)
    found=$(find "$LAUNCH_AGENTS_DIR" -maxdepth 1 -name "${label}.plist" -type f 2>/dev/null || true)
    if [[ -n "$found" ]]; then
        RESURRECTED+=("$found")
    fi
done

if [[ ${#RESURRECTED[@]} -gt 0 ]]; then
    echo ""
    echo "🚨 CICATRIX VIOLATION: Purged plist resurrected in active LaunchAgents dir"
    echo ""
    for plist in "${RESURRECTED[@]}"; do
        echo "  ❌ $plist"
    done
    echo ""
    echo "Per .claude/rules/cicatrix-scars.md (WR2 panel 2026-05-19):"
    echo "  - These plists were formally purged via .disabled-YYYY-MM-DD/ move"
    echo "  - Their presence in active dir IS the sibling-agent resurrection vector"
    echo ""
    echo "To unblock the push:"
    echo "  1. Investigate WHO/WHAT resurrected the plist (sibling claude session?"
    echo "     re-bootstrap script? AI agent via filesystem MCP?)"
    echo "  2. Move plist back to $LAUNCH_AGENTS_DIR/.disabled-$(date +%Y-%m-%d)/"
    echo "  3. If legitimate revival needed, REMOVE label from PURGED_LABELS"
    echo "     in scripts/launchd_cicatrix_lint.sh (requires Zero approval)"
    echo ""
    exit 1
fi

echo "✅ launchd_cicatrix_lint: no purged-plist resurrection detected"
exit 0
