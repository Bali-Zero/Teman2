#!/bin/bash
# docs-guardian — weekly docs hygiene cron
# Sun 05:00 WITA (Sat 21:00 UTC)
#
# Runs docs_sync.py (DOCSYNC markers) + docs_audit.py (inventory).
# Sends a Telegram alert via ~/.claude/scripts/hotfix-notify.sh only when
# docs_audit.py reports a delta (exit code != 0).
set -euo pipefail

# Default to the repo root this script lives in, so cron runs work in-place
# and manual invocations from any worktree also work.
if [[ -n "${REPO:-}" ]]; then
  cd "$REPO"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR/.."
fi

# Cluster + whitelist config — passed as env vars from crontab or defaults.
WHITELIST_ARGS=(
  --whitelist "docs/ARCHITECTURE_DECISION_RECORDS.md"
  --whitelist "docs/API_REFERENCE.md"
  --whitelist "AUTONOMOUS_OPS.md"
  --whitelist "docs/PRO_AIR_CONNECTION.md"
)

CLUSTER_ARGS=(
  --cluster "automation-autonomy:docs/AUTOMATION_AUTONOMY_PLAN_v3_1.md,docs/AUTOMATION_AUTONOMY_SYSTEM_V3_2.md,docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md,docs/AUTOMATION_AUTONOMY_NB1_SUBMISSION.md:docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md"
  --cluster "automations-catalog:docs/ACTIVE_AUTOMATIONS.md,docs/AUTOMATION_MODEL_MAP.md,docs/AUTOMATIONS.md:docs/AUTOMATIONS.md"
  --cluster "system-map:docs/LIVING_ARCHITECTURE.md,docs/SYSTEM_MAP_4D.md,docs/SYSTEM_OVERVIEW.md,docs/CODEBASE_THEMATIC_AREAS.md:docs/LIVING_ARCHITECTURE.md"
  --cluster "system-audit:docs/SYSTEM_AUDIT_2026-04-03.md,docs/SYSTEM_AUDIT_FINAL_2026-04-03.md:docs/SYSTEM_AUDIT_FINAL_2026-04-03.md"
)

# Sync DOCSYNC markers; tolerate failure.
python scripts/docs_sync.py --quiet || true

# Run audit. Capture JSON for alert body before the actual write run.
if ! python scripts/docs_audit.py --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}"; then
  # Delta detected — fetch summary
  STATS=$(python scripts/docs_audit.py --json --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" 2>/dev/null || echo '{}')
  STALE=$(echo "$STATS" | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('stale',0))" 2>/dev/null || echo "?")
  BROKEN=$(echo "$STATS" | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('broken',0))" 2>/dev/null || echo "?")
  ORPHANS=$(echo "$STATS" | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('orphans',0))" 2>/dev/null || echo "?")

  MSG="docs-guardian: delta detected — ${STALE} stale, ${BROKEN} broken, ${ORPHANS} orphans. See docs/DOCS_INVENTORY.md"

  if [[ -x "$HOME/.claude/scripts/hotfix-notify.sh" ]]; then
    "$HOME/.claude/scripts/hotfix-notify.sh" "docs-guardian" "$MSG"
  else
    echo "[docs-guardian] $MSG" >&2
  fi
fi
